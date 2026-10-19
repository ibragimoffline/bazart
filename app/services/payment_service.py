from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import OrderStatus, PaymentStatus, is_admin
from app.models.payment import Payment
from app.models.user import User
from app.money import calc_buyer_premium
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.schemas.payment import HoldCreate, PaymentIntentCreate
from app.services.audit_service import AuditService
from app.services.offer_service import OfferService
from app.services.payment_providers import PaymentProviderError, get_payment_provider
from app.services.payment_state import ALLOWED_TRANSITIONS, assert_payment_transition


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.payments = PaymentRepository(db)

    def create_payment_intent(self, payload: PaymentIntentCreate, buyer: User) -> Payment:
        order = self.orders.get(payload.order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.buyer_id != buyer.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
        if payload.amount != order.final_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount must match order final price",
            )
        if order.status != OrderStatus.PENDING_PAYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is not pending payment",
            )

        try:
            provider = get_payment_provider(payload.provider)
        except PaymentProviderError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        provider_result = provider.create_payment(amount=payload.amount, currency=payload.currency)
        payment = self.payments.create(
            order_id=order.id,
            buyer_id=buyer.id,
            amount=payload.amount,
            currency=payload.currency,
            provider=provider.provider_name,
            provider_payment_id=provider_result.provider_payment_id,
        )
        payment.status = provider_result.status
        self.db.add(payment)
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def confirm_mock_payment(self, payment_id: int, actor: User) -> Payment:
        """Mock to'lovni tasdiqlaydi. FAQAT local/test muhitida.

        Bu metod real pul harakatisiz to'lovni PAID qiladi. Prod'da ochiq
        qolsa — istalgan xaridor bitta so'rov bilan tovarni bepul oladi.
        Shu sababli muhit tekshiruvi eng birinchi qatorda turadi.
        """
        if not settings.allow_mock_payments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        payment = self.payments.get(payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if actor.id != payment.buyer_id and not is_admin(actor.role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment")
        if payment.provider_payment_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment has no provider payment id",
            )

        try:
            provider = get_payment_provider(payment.provider)
        except PaymentProviderError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        provider_result = provider.confirm_payment(provider_payment_id=payment.provider_payment_id)
        payment = self.payments.update_status(payment, provider_result.status)

        if payment.status == PaymentStatus.PAID:
            order = self.orders.get(payment.order_id)
            if order is not None:
                self.orders.update_status(order, OrderStatus.PAID)
        return payment

    # --- Escrow oqimi (Faza D) --------------------------------------------

    def create_hold(self, payload: HoldCreate, buyer: User, ip: str | None = None) -> Payment:
        """Escrow hold yaratadi: PSP kartada mablag'ni bloklaydi.

        Idempotent: bir xil idempotency_key bilan takroriy so'rov yangi hold
        yaratmaydi — mavjudini qaytaradi (ikki marta bloklanish TAQIQ).
        Summa serverdan (order.final_price + buyer premium) hisoblanadi,
        klientdan olinmaydi.
        """
        existing = self.payments.get_by_idempotency_key(payload.idempotency_key)
        if existing is not None:
            # Egalik tekshiruvi: begona kalitli payment oshkor bo'lmasin (IDOR).
            if existing.buyer_id != buyer.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Idempotency key already used"
                )
            # Xato bilan tugagan hold uchun retry: yangi kalit talab qilinadi.
            if existing.status == PaymentStatus.FAILED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Previous attempt failed; use a new idempotency key",
                )
            return existing  # tekshirmasdan qayta yaratish TAQIQ

        order = self.orders.get(payload.order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.buyer_id != buyer.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
        if order.status != OrderStatus.PENDING_PAYMENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Order is not pending payment"
            )

        try:
            provider = get_payment_provider(payload.provider)
        except PaymentProviderError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        amount = order.final_price
        premium = calc_buyer_premium(amount, settings.buyer_premium_bps)
        total = amount + premium

        payment = Payment(
            order_id=order.id,
            buyer_id=buyer.id,
            amount=amount,
            premium=premium,
            total=total,
            currency=payload.currency,
            provider=provider.provider_name,
            status=PaymentStatus.PENDING,
            idempotency_key=payload.idempotency_key,
        )
        self.db.add(payment)
        try:
            # Unique cheklovni HOZIR ishga tushiramiz: parallel bir xil kalitli
            # so'rov IntegrityError oladi va mavjud natijaga qaytadi.
            self.db.flush()
        except IntegrityError:
            # Parallel bir xil kalit: birinchi tranzaksiya hali commit qilmagan
            # bo'lsa mavjud None bo'lishi mumkin — 409 beramiz (None qaytarmaymiz).
            self.db.rollback()
            other = self.payments.get_by_idempotency_key(payload.idempotency_key)
            if other is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Concurrent request in progress; retry",
                ) from None
            return other

        try:
            result = provider.create_hold(
                amount_tiyin=total,
                currency=payload.currency,
                token_reference=payload.token_reference,
                idempotency_key=payload.idempotency_key,
            )
        except PaymentProviderError as exc:
            # Hold amalga oshmadi — FAILED yozib qo'yamiz (dalil qoladi).
            payment.status = PaymentStatus.FAILED
            payment.failed_reason = str(exc)[:255]
            AuditService(self.db).record(
                action="PAYMENT_FAILED",
                entity_type="payment",
                entity_id=payment.id,
                actor_id=buyer.id,
                new_value={"status": PaymentStatus.FAILED.value, "reason": str(exc)[:255]},
                idempotency_key=payload.idempotency_key,
                ip=ip,
            )
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail="Payment hold failed"
            ) from exc

        assert_payment_transition(payment.status, result.status)  # PENDING -> HELD
        payment.status = result.status
        payment.provider_payment_id = result.provider_payment_id
        payment.held_at = datetime.now(UTC)

        order.status = OrderStatus.PICKUP_PENDING
        order.auto_complete_at = datetime.now(UTC) + timedelta(hours=settings.auto_complete_hours)

        AuditService(self.db).record(
            action="PAYMENT_HELD",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=buyer.id,
            new_value={"status": result.status.value, "total": total},
            idempotency_key=payload.idempotency_key,
            ip=ip,
        )
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def capture_payment(
        self, payment_id: int, idempotency_key: str, actor: User | None, ip: str | None = None
    ) -> Payment:
        """Hold'ni capture qiladi: pul sotuvchiga o'tadi, order yakunlanadi.

        Xaridor tovarni tasdiqlaganda yoki auto-complete worker tomonidan
        (actor=None) chaqiriladi. Idempotent: allaqachon RELEASED bo'lsa
        qayta capture qilmaydi. Qatorni FOR UPDATE bilan qulflaydi —
        parallel capture/release poygasi PSP'da ikki settlement bermaydi.
        """
        payment = self.payments.get_for_update(payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if actor is not None and not is_admin(actor.role) and actor.id != payment.buyer_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment")
        if payment.status == PaymentStatus.RELEASED:
            return payment  # idempotent — ikki marta capture qilinmaydi
        if payment.status != PaymentStatus.HELD:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Payment is not in HELD state"
            )

        provider = get_payment_provider(payment.provider)
        result = provider.capture(
            provider_payment_id=payment.provider_payment_id or "",
            idempotency_key=idempotency_key,
        )
        assert_payment_transition(payment.status, result.status)  # HELD -> RELEASED
        payment.status = result.status
        payment.released_at = datetime.now(UTC)

        order = self.orders.get(payment.order_id)
        if order is not None:
            order.status = OrderStatus.COMPLETED

        AuditService(self.db).record(
            action="PAYMENT_RELEASED",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=actor.id if actor is not None else None,
            new_value={"status": result.status.value},
            idempotency_key=idempotency_key,
            ip=ip,
        )
        self.db.commit()
        self.db.refresh(payment)
        return payment

    def release_hold(
        self, payment_id: int, idempotency_key: str, actor: User | None, ip: str | None = None
    ) -> Payment:
        """Hold'ni bekor qiladi: blok ochiladi, pul xaridorda qoladi.

        FAQAT admin (nizo qarori) yoki tizim (actor=None) chaqira oladi.
        Xaridor O'ZI release qila OLMAYDI — aks holda tovarni olgach hold'ni
        bekor qilib pulni qaytarib olardi (escrow himoyasi teshigi, review
        KRITIK topilmasi). Qatorni FOR UPDATE bilan qulflaydi.
        """
        payment = self.payments.get_for_update(payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if actor is not None and not is_admin(actor.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only an admin can release a hold (open a dispute instead)",
            )
        if payment.status == PaymentStatus.CANCELLED_HOLD:
            return payment  # idempotent
        if payment.status != PaymentStatus.HELD:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Payment is not in HELD state"
            )

        provider = get_payment_provider(payment.provider)
        result = provider.release(
            provider_payment_id=payment.provider_payment_id or "",
            idempotency_key=idempotency_key,
        )
        assert_payment_transition(payment.status, result.status)  # HELD -> CANCELLED_HOLD
        payment.status = result.status

        order = self.orders.get(payment.order_id)
        if order is not None and order.status != OrderStatus.CANCELLED:
            order.status = OrderStatus.CANCELLED
            # Taklif bitimi bekor bo'ldi — donalar zaxiraga qaytadi (shu tranzaksiyada).
            OfferService(self.db).restore_stock(order)

        AuditService(self.db).record(
            action="PAYMENT_CANCELLED_HOLD",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=actor.id if actor is not None else None,
            new_value={"status": result.status.value},
            idempotency_key=idempotency_key,
            ip=ip,
        )
        self.db.commit()
        self.db.refresh(payment)
        return payment

    # --- Webhook reconciliation (PSP = haqiqat manbai) --------------------

    def reconcile_from_webhook(
        self,
        *,
        provider: str,
        provider_payment_id: str,
        target_status: PaymentStatus,
        event_id: str,
    ) -> bool:
        """PSP webhook hodisasidan payment/order holatini yangilaydi.

        Haqiqat manbai — PSP. Bu metod webhook tranzaksiyasi ICHIDA chaqiriladi
        va COMMIT QILMAYDI (WebhookService bir marta commit qiladi) — hodisa
        yozuvi va payment o'zgarishi atomik bo'lishi uchun.

        Idempotent va xavfsiz:
          - Payment topilmasa (begona/eski id) — jimgina o'tkazib yuboradi.
          - Allaqachon target holatda bo'lsa — o'zgartirmaydi (takroriy webhook).
          - Taqiqlangan o'tish bo'lsa (masalan RELEASED ustiga cancel) — HECH
            NARSA o'zgartirmaydi, anomaliyani audit qiladi (webhook 500 bermaydi,
            aks holda PSP cheksiz retry qiladi).

        :returns: holat haqiqatan o'zgarganda True.
        """
        payment = self.payments.get_for_update_by_provider_payment_id(provider, provider_payment_id)
        if payment is None:
            return False  # noma'lum to'lov — yon effektsiz o'tkazib yuboramiz
        if payment.status == target_status:
            return False  # allaqachon shu holatda — idempotent no-op

        if target_status not in ALLOWED_TRANSITIONS.get(payment.status, frozenset()):
            # PSP kutilmagan o'tishni bildirdi — o'zgartirmaymiz, lekin dalil qoldiramiz.
            AuditService(self.db).record(
                action="PAYMENT_WEBHOOK_IGNORED",
                entity_type="payment",
                entity_id=payment.id,
                actor_id=None,
                old_value={"status": payment.status.value},
                new_value={"status": target_status.value, "event_id": event_id},
            )
            return False

        old_status = payment.status
        payment.status = target_status
        now = datetime.now(UTC)
        if target_status == PaymentStatus.HELD:
            payment.held_at = payment.held_at or now
        elif target_status == PaymentStatus.RELEASED:
            payment.released_at = now

        order = self.orders.get(payment.order_id)
        if order is not None:
            if target_status == PaymentStatus.HELD and order.status == OrderStatus.PENDING_PAYMENT:
                order.status = OrderStatus.PICKUP_PENDING
                order.auto_complete_at = now + timedelta(hours=settings.auto_complete_hours)
            elif target_status == PaymentStatus.RELEASED:
                order.status = OrderStatus.COMPLETED
            elif (
                target_status == PaymentStatus.CANCELLED_HOLD
                and order.status != OrderStatus.CANCELLED
            ):
                order.status = OrderStatus.CANCELLED
                OfferService(self.db).restore_stock(order)

        AuditService(self.db).record(
            action=f"PAYMENT_WEBHOOK_{target_status.value.upper()}",
            entity_type="payment",
            entity_id=payment.id,
            actor_id=None,  # PSP webhook — odam aktori yo'q
            old_value={"status": old_status.value},
            new_value={"status": target_status.value, "event_id": event_id},
        )
        return True

    def get_payment_by_order(self, order_id: int, actor: User) -> Payment:
        order = self.orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if not is_admin(actor.role) and actor.id not in {order.buyer_id, order.seller_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")

        payment = self.payments.get_latest_by_order(order_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment
