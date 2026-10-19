"""Taklifli savdo (offer marketplace): e'lon qilish, taklif, qarshi taklif, qabul.

Asosiy qoidalar (docs/OFFERS.md):
- Sotuvchi mo'ljal narx (DONA uchun) va miqdor beradi. Bu majburiy chegara EMAS:
  xaridor istalgan musbat narx taklif qila oladi — pastroq ham, yuqoriroq ham.
  Min qadam, "oldingidan yuqori bo'lsin" qoidasi, avtomatik rad etish YO'Q.
- Xaridor miqdorni tanlaydi (<= qolgan zaxira). Jami = miqdor x dona narxi.
- Javob navbati (`awaiting`) kimda bo'lsa, o'sha qabul qiladi, rad etadi yoki
  qarshi taklif beradi. Javobsiz taklif OFFER_TTL dan keyin muddati o'tadi.
- E'londa majburiy muddat bor (3/5/7 kun) — Bazart'ning asosiy g'oyasi.

ZAXIRA va POYGA: qabul qilish e'lon qatorini FOR UPDATE bilan qulflaydi va order'ni
shu tranzaksiyada yaratadi. Zaxira esa shartli UPDATE bilan ayiriladi
(`take_stock`: `WHERE quantity_available >= q`) — qulf bo'lmasa ham lost update
bo'lmaydi. Qulf tartibi har joyda bir xil — avval item, keyin offer (deadlock yo'q).
DIQQAT: bazadagi CHECK (0..quantity_total) faqat manfiy qiymatni ushlaydi, lost
update'ni EMAS — himoya qulf + shartli UPDATE'da.
"""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import (
    ItemStatus,
    ListingType,
    NotificationType,
    OfferParty,
    OfferStatus,
    is_admin,
)
from app.models.item import Item
from app.models.offer import Offer
from app.models.order import Order
from app.models.user import User
from app.money import format_soum_text
from app.repositories.offer_repository import OfferRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.item import ItemPublish
from app.schemas.offer import OfferCounter, OfferCreate
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Javobsiz taklif shuncha vaqtdan keyin muddati o'tadi (har qarshi taklifda qayta).
OFFER_TTL = timedelta(hours=48)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _other(party: OfferParty) -> OfferParty:
    return OfferParty.SELLER if party == OfferParty.BUYER else OfferParty.BUYER


def _som(tiyin: int) -> str:
    return f"{format_soum_text(tiyin)} soʻm"


class OfferService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.offers = OfferRepository(db)

    # --- E'lon qilish ---------------------------------------------------------

    def publish(self, item_id: int, seller: User, payload: ItemPublish) -> Item:
        """Qoralamani taklifli e'lon qiladi yoki muddati o'tgan e'lonni qayta ochadi."""
        try:
            item = self.offers.lock_item(item_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
            if item.seller_id != seller.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item")

            first_publish = (
                item.listing_type is None
                and item.status == ItemStatus.DRAFT
                and item.auction is None
            )
            republish = (
                item.listing_type == ListingType.OFFER
                and item.status == ItemStatus.EXPIRED
                and item.quantity_available > 0
            )
            if not (first_publish or republish):
                raise _conflict("Only a draft or an expired offer listing can be published")

            now = datetime.now(UTC)
            item.listing_type = ListingType.OFFER
            item.status = ItemStatus.ACTIVE
            item.listing_duration_days = payload.duration_days
            item.listing_ends_at = now + timedelta(days=payload.duration_days)
            item.published_at = item.published_at or now
            self.db.add(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(item)
        return item

    # --- Taklif berish --------------------------------------------------------

    def make_offer(self, item_id: int, buyer: User, payload: OfferCreate) -> Offer:
        try:
            item = self.offers.lock_item(item_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
            if item.seller_id == buyer.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot make an offer on your own item",
                )
            now = datetime.now(UTC)
            self._ensure_open_listing(item, now)
            self._ensure_stock(item, payload.quantity)
            if self.offers.get_open_for_buyer(item.id, buyer.id) is not None:
                raise _conflict(
                    "You already have an open offer on this item; counter or withdraw it"
                )

            offer = Offer(
                item_id=item.id,
                buyer_id=buyer.id,
                seller_id=item.seller_id,
                quantity=payload.quantity,
                unit_price=payload.unit_price,
                status=OfferStatus.PENDING,
                awaiting=OfferParty.SELLER,
                expires_at=self._expiry(item, now),
            )
            self.db.add(offer)
            self.offers.add_event(
                offer,
                actor=OfferParty.BUYER,
                action="offer",
                quantity=payload.quantity,
                unit_price=payload.unit_price,
                message=payload.message,
            )
            self.db.flush()
            NotificationService(self.db).create(
                user_id=item.seller_id,
                type=NotificationType.OFFER_RECEIVED,
                title="Yangi narx taklifi",
                body=(
                    f"«{item.title}»: {payload.quantity} dona x {_som(payload.unit_price)} "
                    f"(jami {_som(offer.total_price)})."
                ),
                payload={"offer_id": offer.id, "item_id": item.id},
            )
            self.db.commit()
        except IntegrityError as exc:
            # Parallel ikki so'rov: uq_offers_open_per_buyer ikkinchisini to'xtatadi.
            self.db.rollback()
            raise _conflict("You already have an open offer on this item") from exc
        except Exception:
            self.db.rollback()
            raise
        return self._reload(offer.id)

    # --- Javoblar -------------------------------------------------------------

    def counter(self, offer_id: int, actor: User, payload: OfferCounter) -> Offer:
        try:
            item, offer, party = self._lock_for_response(offer_id, actor)
            now = datetime.now(UTC)
            self._ensure_turn(offer, party)
            self._ensure_stock(item, payload.quantity)

            offer.quantity = payload.quantity
            offer.unit_price = payload.unit_price
            offer.awaiting = _other(party)
            offer.expires_at = self._expiry(item, now)
            self.offers.add_event(
                offer,
                actor=party,
                action="counter",
                quantity=payload.quantity,
                unit_price=payload.unit_price,
                message=payload.message,
            )
            NotificationService(self.db).create(
                user_id=offer.buyer_id if party == OfferParty.SELLER else offer.seller_id,
                type=NotificationType.OFFER_COUNTERED,
                title="Qarshi taklif",
                body=(
                    f"«{item.title}»: {payload.quantity} dona x {_som(payload.unit_price)} "
                    f"(jami {_som(offer.total_price)}). Javobingiz kutilmoqda."
                ),
                payload={"offer_id": offer.id, "item_id": item.id},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._reload(offer.id)

    def accept(self, offer_id: int, actor: User) -> Offer:
        """Navbatdagi tomon shartlarni qabul qiladi: zaxira kamayadi, order yaratiladi."""
        try:
            item, offer, party = self._lock_for_response(offer_id, actor)
            self._ensure_turn(offer, party)
            self._ensure_stock(item, offer.quantity)

            remaining = self.offers.take_stock(item.id, offer.quantity)
            if remaining is None:
                raise _conflict(f"Only {item.quantity_available} unit(s) available")
            self.db.refresh(item)
            offer.status = OfferStatus.ACCEPTED
            self.offers.add_event(
                offer,
                actor=party,
                action="accept",
                quantity=offer.quantity,
                unit_price=offer.unit_price,
            )
            order = OrderRepository(self.db).create_for_offer(offer)

            notifier = NotificationService(self.db)
            total = _som(order.final_price)
            notifier.create(
                user_id=offer.buyer_id,
                type=NotificationType.OFFER_ACCEPTED,
                title="Taklif qabul qilindi",
                body=(
                    f"«{item.title}»: {offer.quantity} dona, jami {total}. "
                    "Toʻlovni amalga oshiring — pul escrow'da himoyalanadi."
                ),
                payload={"offer_id": offer.id, "item_id": item.id, "order_id": order.id},
            )
            notifier.create(
                user_id=offer.seller_id,
                type=NotificationType.OFFER_ACCEPTED,
                title="Bitim tuzildi",
                body=(
                    f"«{item.title}»: {offer.quantity} dona, jami {total}. "
                    "Xaridor toʻlovi kutilmoqda."
                ),
                payload={"offer_id": offer.id, "item_id": item.id, "order_id": order.id},
            )

            if item.quantity_available == 0:
                item.status = ItemStatus.SOLD
                # Zaxira tugadi — qolgan ochiq takliflar yopiladi (javob kutib qolmasin).
                for other in self.offers.list_open_for_item(item.id, exclude_id=offer.id):
                    self._close(other, OfferStatus.REJECTED, "sold_out", item)
            self.db.add(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._reload(offer.id)

    def reject(self, offer_id: int, actor: User) -> Offer:
        """Sotuvchi istalgan ochiq taklifni rad eta oladi; xaridor — faqat qarshi taklifni."""
        try:
            item, offer, party = self._lock_for_response(offer_id, actor)
            if party == OfferParty.BUYER:
                self._ensure_turn(offer, party)
            self._close(offer, OfferStatus.REJECTED, "reject", item, actor=party)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._reload(offer.id)

    def withdraw(self, offer_id: int, actor: User) -> Offer:
        """Xaridor o'z ochiq taklifini istalgan payt qaytarib oladi."""
        try:
            item, offer, party = self._lock_for_response(offer_id, actor)
            if party != OfferParty.BUYER:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the buyer can withdraw an offer",
                )
            self._close(offer, OfferStatus.WITHDRAWN, "withdraw", item, actor=party)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._reload(offer.id)

    # --- O'qish ---------------------------------------------------------------

    def get_for_user(self, offer_id: int, user: User) -> Offer:
        offer = self.offers.get(offer_id)
        if offer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
        if user.id not in (offer.buyer_id, offer.seller_id) and not is_admin(user.role):
            # Begona taklifning mavjudligini ham oshkor qilmaymiz (IDOR).
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
        return offer

    def list_for_item(self, item_id: int, user: User) -> list[Offer]:
        """Sotuvchi (va admin) — barcha takliflar; boshqa foydalanuvchi — faqat o'ziniki."""
        item = self.db.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        if item.seller_id == user.id or is_admin(user.role):
            return self.offers.list_for_item(item_id)
        return self.offers.list_for_item(item_id, buyer_id=user.id)

    def list_mine(
        self, user: User, role: OfferParty, offer_status: OfferStatus | None
    ) -> list[Offer]:
        return self.offers.list_for_user(user.id, role, status=offer_status)

    # --- Boshqa oqimlar uchun ilgaklar ---------------------------------------

    def cancel_listing(self, item_id: int) -> Item:
        """Taklifli e'lonni olib tashlaydi: qolgan zaxira sotuvdan chiqadi, ochiq
        takliflar yopiladi. Allaqachon tuzilgan bitimlar (order'lar) o'z kuchida qoladi.

        Qabul qilish bilan bir xil qulf (item FOR UPDATE) — bekor qilish va parallel
        qabul qilish poyga qilmaydi. Huquq tekshiruvi chaqiruvchida (ItemService).
        """
        try:
            item = self.offers.lock_item(item_id)
            if item is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
            if item.status == ItemStatus.SOLD:
                raise _conflict("Sold item cannot be cancelled")
            if item.status != ItemStatus.CANCELLED:
                item.status = ItemStatus.CANCELLED
                self.close_open_offers(item)
                self.db.add(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(item)
        return item

    def close_open_offers(self, item: Item, action: str = "cancel") -> None:
        """E'lon bekor qilinganda / rad etilganda ochiq takliflarni yopadi. COMMIT QILMAYDI."""
        for offer in self.offers.list_open_for_item(item.id):
            self._close(offer, OfferStatus.REJECTED, action, item)

    def restore_stock(self, order: Order) -> None:
        """Bekor qilingan order (to'lanmadi / hold qaytarildi) donalarini zaxiraga qaytaradi.

        COMMIT QILMAYDI — order holatini o'zgartirgan tranzaksiya ichida chaqiriladi.
        Auksion order'lari uchun hech narsa qilmaydi.
        """
        if order.offer_id is None:
            return
        item = self.offers.lock_item(order.item_id)
        if item is None:
            return
        item.quantity_available = min(item.quantity_total, item.quantity_available + order.quantity)
        if item.status == ItemStatus.SOLD:
            ends = item.listing_ends_at
            still_open = ends is not None and _as_utc(ends) > datetime.now(UTC)
            item.status = ItemStatus.ACTIVE if still_open else ItemStatus.EXPIRED
        self.db.add(item)

    # --- Fon vazifasi ---------------------------------------------------------

    def expire_due(self) -> tuple[int, int]:
        """Muddati o'tgan takliflar va e'lonlarni yopadi. (takliflar, e'lonlar) soni.

        To'g'rilik bu vazifaga bog'liq EMAS: har javob (qabul/qarshi) muddatni o'zi
        tekshiradi. Bu yerda faqat holat tartibga keltiriladi va xabar yuboriladi.
        Har yozuv alohida tranzaksiyada — bittasining xatosi qolganini to'xtatmaydi.
        """
        now = datetime.now(UTC)
        offers_done = listings_done = 0

        for item_id in self.offers.list_due_listing_ids(now):
            try:
                item = self.offers.lock_item(item_id)
                if (
                    item is not None
                    and item.status == ItemStatus.ACTIVE
                    and item.listing_ends_at is not None
                    and _as_utc(item.listing_ends_at) <= now
                ):
                    item.status = ItemStatus.EXPIRED
                    for offer in self.offers.list_open_for_item(item.id):
                        self._close(offer, OfferStatus.EXPIRED, "expire", item)
                    listings_done += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("OFFER: e'lon=%s muddatini yopib bo'lmadi", item_id)

        for offer_id in self.offers.list_due_offer_ids(now):
            try:
                offer = self.offers.get(offer_id)
                if offer is None:
                    continue
                item = self.offers.lock_item(offer.item_id)
                offer = self.offers.get_for_update(offer_id)
                if (
                    offer is not None
                    and offer.status == OfferStatus.PENDING
                    and _as_utc(offer.expires_at) <= now
                ):
                    self._close(offer, OfferStatus.EXPIRED, "expire", item)
                    offers_done += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                logger.exception("OFFER: taklif=%s muddatini yopib bo'lmadi", offer_id)

        return offers_done, listings_done

    # --- Ichki yordamchilar ---------------------------------------------------

    def _lock_for_response(self, offer_id: int, actor: User) -> tuple[Item, Offer, OfferParty]:
        """Item -> offer tartibida qulflaydi, ishtirokchi va holatni tekshiradi."""
        found = self.offers.get(offer_id)
        if found is None or actor.id not in (found.buyer_id, found.seller_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
        item = self.offers.lock_item(found.item_id)
        offer = self.offers.get_for_update(offer_id)
        if item is None or offer is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
        self.db.refresh(offer)
        if offer.status != OfferStatus.PENDING:
            raise _conflict(f"Offer is already {offer.status.value}")

        now = datetime.now(UTC)
        if _as_utc(offer.expires_at) <= now:
            self._close(offer, OfferStatus.EXPIRED, "expire", item)
            self.db.commit()
            raise _conflict("Offer has expired")
        self._ensure_open_listing(item, now)
        party = OfferParty.BUYER if actor.id == offer.buyer_id else OfferParty.SELLER
        return item, offer, party

    @staticmethod
    def _ensure_open_listing(item: Item, now: datetime) -> None:
        if item.listing_type != ListingType.OFFER:
            raise _conflict("This item is not an offer listing")
        if item.status != ItemStatus.ACTIVE:
            raise _conflict("Listing is not active")
        if item.listing_ends_at is None or _as_utc(item.listing_ends_at) <= now:
            raise _conflict("Listing has ended")

    @staticmethod
    def _ensure_stock(item: Item, quantity: int) -> None:
        if quantity > item.quantity_available:
            raise _conflict(f"Only {item.quantity_available} unit(s) available")

    @staticmethod
    def _ensure_turn(offer: Offer, party: OfferParty) -> None:
        if offer.awaiting != party:
            raise _conflict("Waiting for the other party to respond")

    @staticmethod
    def _expiry(item: Item, now: datetime) -> datetime:
        """Taklif muddati: 48 soat, lekin e'lon muddatidan oshmaydi."""
        ttl_end = now + OFFER_TTL
        ends = item.listing_ends_at
        return min(ttl_end, _as_utc(ends)) if ends is not None else ttl_end

    def _close(
        self,
        offer: Offer,
        new_status: OfferStatus,
        action: str,
        item: Item | None,
        *,
        actor: OfferParty | None = None,
    ) -> None:
        offer.status = new_status
        self.offers.add_event(offer, actor=actor, action=action)
        title = item.title if item is not None else "Eʼlon"
        reasons = {
            "reject": "rad etildi",
            "withdraw": "xaridor tomonidan qaytarib olindi",
            "expire": "muddati oʻtdi",
            "sold_out": "yopildi — mahsulot tugadi",
            "cancel": "yopildi — eʼlon olib tashlandi",
        }
        # Harakat qilgan tomonga xabar shart emas; tizim yopsa — ikkalasiga.
        recipients = []
        if actor != OfferParty.BUYER:
            recipients.append(offer.buyer_id)
        if actor != OfferParty.SELLER and action in ("withdraw", "expire", "reject"):
            recipients.append(offer.seller_id)
        notifier = NotificationService(self.db)
        for user_id in recipients:
            notifier.create(
                user_id=user_id,
                type=NotificationType.OFFER_CLOSED,
                title="Taklif yopildi",
                body=f"«{title}» boʻyicha taklif {reasons.get(action, 'yopildi')}.",
                payload={"offer_id": offer.id, "item_id": offer.item_id},
            )

    def _reload(self, offer_id: int) -> Offer:
        self.db.expire_all()
        offer = self.offers.get(offer_id)
        assert offer is not None
        return offer
