from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auction import Auction
from app.models.complaint import Complaint
from app.models.deal import Deal
from app.models.enums import (
    ComplaintStatus,
    ComplaintTargetType,
    DealCancelReason,
    DealStatus,
    ItemStatus,
    NotificationType,
    is_admin,
)
from app.models.offer import Offer
from app.models.user import User
from app.money import Tiyin, calc_line_total, format_soum_text
from app.repositories.deal_repository import DealRepository
from app.repositories.offer_repository import OfferRepository
from app.schemas.deal import DealContact, DealDetail
from app.services.deal_state import InvalidDealTransition, assert_deal_transition
from app.services.notification_service import NotificationService


class DealService:
    """Kelishuv: yaratish, ko'rish va amallar (docs/DEALS.md). Holat faqat `deal_state` orqali."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.deals = DealRepository(db)

    # --- Yaratish: YAGONA kirish nuqtasi (E2.4) ---------------------------------

    def create_deal(
        self,
        *,
        item_id: int,
        buyer_id: int,
        seller_id: int,
        unit_price: Tiyin,
        quantity: int = 1,
        auction_id: int | None = None,
        offer_id: int | None = None,
    ) -> Deal:
        """Kelishuvni yaratadi. Barcha manbalar (taklif qabuli, auksion g'olibi, buy-now,
        tushuvchi narx, keyingi bidderga taklif) SHU yerdan o'tadi — E5 komissiyasi va
        bildirishnomalar aynan shu nuqtaga ulanadi. Boshqa joyda `Deal(...)` yaratilmaydi
        (test_deal_entry_point qo'riqlaydi).

        COMMIT QILMAYDI: chaqiruvchining tranzaksiyasi (zaxira kamayishi, auksion yopilishi)
        bilan birga atomik yoziladi. Kelishuv `agreed` da tug'iladi — kontaktlar shu lahzada
        ochiladi (`contacts_revealed_at`).
        """
        deal = Deal(
            item_id=item_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            auction_id=auction_id,
            offer_id=offer_id,
            quantity=quantity,
            unit_price=unit_price,
            final_price=calc_line_total(unit_price, quantity),
            status=DealStatus.AGREED,
            contacts_revealed_at=datetime.now(UTC),
        )
        self.deals.add(deal)
        _notify_created(self.db, deal)
        return deal

    def create_for_winning_auction(self, auction: Auction) -> Deal | None:
        """Auksion g'olibi (yopilish, buy-now, tushuvchi narx, keyingi bidder). Idempotent."""
        if auction.winner_id is None or auction.winning_bid is None:
            return None
        existing = self.deals.get_active_by_auction_id(auction.id)
        if existing is not None:
            return existing
        return self.create_deal(
            item_id=auction.item_id,
            buyer_id=auction.winner_id,
            seller_id=auction.seller_id,
            unit_price=auction.winning_bid.amount,
            auction_id=auction.id,
        )

    def create_for_offer(self, offer: Offer) -> Deal:
        """Qabul qilingan taklif: miqdor x kelishilgan dona narxi."""
        return self.create_deal(
            item_id=offer.item_id,
            buyer_id=offer.buyer_id,
            seller_id=offer.seller_id,
            unit_price=offer.unit_price,
            quantity=offer.quantity,
            offer_id=offer.id,
        )

    def get_deal_for_user(self, deal_id: int, user: User) -> Deal:
        """Ishtirokchi yoki admin. Begona — 404 (kelishuv mavjudligi ham oshkor bo'lmaydi)."""
        deal = self.deals.get(deal_id)
        if deal is None or not (is_admin(user.role) or user.id in {deal.buyer_id, deal.seller_id}):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        return deal

    def detail_for_user(self, deal_id: int, user: User) -> DealDetail:
        """Kelishuv + ikkinchi tomon kontakti (docs/DEALS.md §4).

        Kontakt faqat ISHTIROKCHIGA (admin ham emas) va faqat `contacts_revealed_at` dan keyin.
        Ochilgan kontakt kelishuv bekor bo'lsa ham qayta yashirilmaydi (raqam allaqachon ma'lum).
        """
        deal = self.get_deal_for_user(deal_id, user)
        detail = DealDetail.model_validate(deal)
        participant = user.id in {deal.buyer_id, deal.seller_id}
        if participant and deal.contacts_revealed_at is not None:
            other = deal.seller if user.id == deal.buyer_id else deal.buyer
            detail.counterparty = DealContact(
                user_id=other.id,
                full_name=other.full_name,
                phone=other.phone if other.phone_verified_at is not None else None,
                telegram_username=other.telegram_username,
            )
        return detail

    def list_buyer_deals(self, buyer: User) -> list[Deal]:
        return self.deals.list_for_buyer(buyer.id)

    def list_seller_deals(self, seller: User) -> list[Deal]:
        return self.deals.list_for_seller(seller.id)

    def list_admin_deals(self, admin: User) -> list[Deal]:
        if not is_admin(admin.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )
        return self.deals.list_all()

    # --- Amallar (docs/DEALS.md §5) -------------------------------------------

    def complete(self, deal_id: int, actor: User) -> Deal:
        """Sotuvchi "Sotildi" belgilaydi. Xaridor allaqachon tasdiqlagan bo'lsa — completed."""
        deal = self._lock_open(deal_id, actor)
        if actor.id != deal.seller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Faqat sotuvchi belgilay oladi"
            )
        first_mark = deal.seller_marked_sold_at is None
        if first_mark:
            deal.seller_marked_sold_at = datetime.now(UTC)
        if deal.buyer_confirmed_at is not None:
            self._complete(deal)
        elif first_mark:
            _notify_marked_sold(self.db, deal)
        return self._save(deal)

    def confirm(self, deal_id: int, actor: User) -> Deal:
        """Xaridor tasdiqlaydi. Sotuvchi "Sotildi" belgilagan bo'lsa — completed; aks holda
        tasdiq yoziladi va sotuvchi belgilashi bilan kelishuv darhol yakunlanadi."""
        deal = self._lock_open(deal_id, actor)
        if actor.id != deal.buyer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Faqat xaridor tasdiqlay oladi"
            )
        if deal.buyer_confirmed_at is None:
            deal.buyer_confirmed_at = datetime.now(UTC)
        if deal.seller_marked_sold_at is not None:
            self._complete(deal)
        return self._save(deal)

    def cancel(self, deal_id: int, actor: User, reason: DealCancelReason) -> Deal:
        """Istalgan tomon (yoki admin) sabab bilan bekor qiladi.

        `no_response` faqat bog'lanish oynasidan (48 soat) keyin — aks holda bir tomon
        ikkinchisini darhol "javob bermadi" deb ayblab, hisoblagich yozdira olardi.
        Aybdor tomon sababdan aniqlanadi (`at_fault_for`). Taklif kelishuvida donalar
        zaxiraga qaytadi.
        """
        deal = self._lock_open(deal_id, actor, allow_admin=True)
        if reason == DealCancelReason.NO_RESPONSE:
            opened = deal.contacts_revealed_at or deal.created_at
            window = timedelta(hours=settings.deal_contact_window_hours)
            if datetime.now(UTC) < _aware(opened) + window:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="no_response faqat bog'lanish oynasidan keyin "
                    f"({settings.deal_contact_window_hours} soat)",
                )
        self._transition(deal, DealStatus.CANCELLED)
        deal.cancelled_at = datetime.now(UTC)
        deal.cancelled_by_id = actor.id
        deal.cancel_reason = reason
        deal.at_fault_id = at_fault_for(deal, actor.id, reason)
        self._restore_stock(deal)
        _notify_cancelled(self.db, deal, actor.id)
        return self._save(deal)

    # --- Fon vazifasi (E2.7) -----------------------------------------------------

    def auto_confirm_due(self, now: datetime | None = None) -> int:
        """ "Sotildi" dan `deal_auto_confirm_hours` o'tgan, xaridor jim va ochiq shikoyat
        yo'q kelishuvlarni yakunlaydi. Yakunlanganlar soni.

        Ochiq (OPEN/REVIEWING) shikoyat avto-tasdiqni to'xtatadi — aks holda nizoli kelishuv
        "muvaffaqiyatli" hisoblanib, sharh va hisoblagichlarga tushardi. `SKIP LOCKED`: shu
        payt foydalanuvchi amali qulflagan kelishuv keyingi tik'ka qoladi, ikki worker
        bir kelishuvni ikki marta yakunlamaydi.
        """
        now = now or datetime.now(UTC)
        cutoff = now - timedelta(hours=settings.deal_auto_confirm_hours)
        open_complaint = exists().where(
            Complaint.target_type == ComplaintTargetType.DEAL,
            Complaint.target_id == Deal.id,
            Complaint.status.in_([ComplaintStatus.OPEN, ComplaintStatus.REVIEWING]),
        )
        due = self.db.scalars(
            select(Deal)
            .where(
                Deal.status == DealStatus.AGREED,
                Deal.seller_marked_sold_at.is_not(None),
                Deal.seller_marked_sold_at <= cutoff,
                ~open_complaint,
            )
            .with_for_update(skip_locked=True)
        ).all()
        for deal in due:
            self._complete(deal, now, auto=True)
            self.db.add(deal)
        self.db.commit()
        return len(due)

    # --- Ichki ------------------------------------------------------------------

    def _lock_open(self, deal_id: int, actor: User, *, allow_admin: bool = False) -> Deal:
        """Ochiq (`agreed`) kelishuvni qulflab oladi; begona — 404 (mavjudligi oshkor bo'lmaydi).

        Yakuniy holatdagi kelishuvga hech qanday amal yo'q (409) — "Sotildi"/"Tasdiqlayman"
        o'tishsiz ham vaqt yozadi, shuning uchun holat shu yerda tekshiriladi.
        """
        deal = self.deals.get_for_update(deal_id)
        participant = deal is not None and actor.id in {deal.buyer_id, deal.seller_id}
        if deal is None or not (participant or (allow_admin and is_admin(actor.role))):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        if deal.status != DealStatus.AGREED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Kelishuv {deal.status.value} holatida — amal mumkin emas",
            )
        return deal

    def _complete(self, deal: Deal, now: datetime | None = None, *, auto: bool = False) -> None:
        """agreed -> completed + ikkala tomonga xabar (bir marta: o'tish faqat agreed'dan)."""
        self._transition(deal, DealStatus.COMPLETED)
        deal.completed_at = now or datetime.now(UTC)
        _notify_completed(self.db, deal, auto=auto)

    def _transition(self, deal: Deal, target: DealStatus) -> None:
        try:
            assert_deal_transition(deal.status, target)
        except InvalidDealTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        deal.status = target

    def _restore_stock(self, deal: Deal) -> None:
        """Bekor qilingan taklif kelishuvining donalarini zaxiraga qaytaradi. COMMIT QILMAYDI.

        Auksion kelishuvlarida hech narsa qilmaydi (mahsulot holati E3.7 da). Qulf tartibi:
        kelishuv (allaqachon qulflangan), keyin e'lon.
        """
        if deal.offer_id is None:
            return
        item = OfferRepository(self.db).lock_item(deal.item_id)
        if item is None:
            return
        item.quantity_available = min(item.quantity_total, item.quantity_available + deal.quantity)
        if item.status == ItemStatus.SOLD:
            ends = item.listing_ends_at
            still_open = ends is not None and _aware(ends) > datetime.now(UTC)
            item.status = ItemStatus.ACTIVE if still_open else ItemStatus.EXPIRED
        self.db.add(item)

    def _save(self, deal: Deal) -> Deal:
        self.db.add(deal)
        self.db.commit()
        self.db.refresh(deal)
        return deal


def at_fault_for(deal: Deal, actor_id: int, reason: DealCancelReason) -> int | None:
    """Bekor qilishda aybdor tomon (docs/DEALS.md §7).

    no_response -> bekor qilmagan tomon; not_as_described -> sotuvchi; changed_mind va
    other -> bekor qilgan tomon. Admin (ishtirokchi emas) bekor qilsa va sabab tomonni
    ko'rsatmasa — aybdor yo'q.
    """
    participant = actor_id in {deal.buyer_id, deal.seller_id}
    if reason == DealCancelReason.NOT_AS_DESCRIBED:
        return deal.seller_id
    if not participant:
        return None
    if reason == DealCancelReason.NO_RESPONSE:
        return deal.buyer_id if actor_id == deal.seller_id else deal.seller_id
    return actor_id


def _aware(value: datetime) -> datetime:
    """Eski ustunlar (timestamp without time zone) UTC deb hisoblanadi."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# --- Bildirishnomalar (E2.12) -------------------------------------------------------------
#
# Matnda va payload'da telefon/Telegram YO'Q: bildirishnoma Telegram'ga ketadi va DB'da oddiy
# matn sifatida saqlanadi. Kontakt faqat IDOR-himoyali GET /deals/{id} orqali. Hammasi
# chaqiruvchining tranzaksiyasida (commit yo'q) — kelishuv bekor bo'lsa xabar ham yo'q,
# tashqi yetkazish esa commit'dan keyin (notification_service).

CANCEL_REASON_TEXT: dict[DealCancelReason, str] = {
    # Betaraf: "javob bermadi" ayblovi o'rniga — xaridor ham, sotuvchi ham shuni o'qiydi.
    DealCancelReason.NO_RESPONSE: "tomonlar bog'lana olmadi",
    DealCancelReason.CHANGED_MIND: "ikkinchi tomon kelishuvdan voz kechdi",
    DealCancelReason.NOT_AS_DESCRIBED: "mahsulot e'londagi tavsifga mos kelmadi",
    DealCancelReason.OTHER: "boshqa sabab",
}


def contact_notice(deal: Deal) -> str:
    """Kontaktlar haqidagi jumla — HOLATGA qarab. E5 da `fee_pending` (kontaktlar yopiq)
    uchun alohida tarmoq qo'shiladi; `agreed` matni o'zgarmaydi."""
    if deal.status == DealStatus.AGREED:
        return "Kontaktlar ochildi — kelishuv sahifasiga o'ting."
    return "Holatni kelishuv sahifasida kuzating."


def _payload(deal: Deal, **extra: object) -> dict:
    payload: dict = {"deal_id": deal.id, "item_id": deal.item_id}
    if deal.auction_id is not None:
        payload["auction_id"] = deal.auction_id
    if deal.offer_id is not None:
        payload["offer_id"] = deal.offer_id
    return {**payload, **extra}


def _title(deal: Deal) -> str:
    return deal.item.title if deal.item is not None else f"#{deal.item_id}"


def _notify_created(db: Session, deal: Deal) -> None:
    """Kelishuv tuzildi: manbaga qarab mavjud turlar (auksion — WON/SOLD, taklif —
    OFFER_ACCEPTED), lekin bitta joydan — har kelishuvga aniq bir juftlik."""
    qty = f"{deal.quantity} dona, jami " if deal.quantity > 1 else ""
    body = (
        f"«{_title(deal)}»: {qty}{format_soum_text(deal.final_price)} soʻm. {contact_notice(deal)}"
    )
    payload = _payload(deal, final_price=str(deal.final_price))
    notifier = NotificationService(db)
    if deal.auction_id is not None:
        buyer = (NotificationType.WON, "Kelishuv tuzildi — mahsulot sizniki")
        seller = (NotificationType.SOLD, "Kelishuv tuzildi — xaridor topildi")
    else:
        buyer = (NotificationType.OFFER_ACCEPTED, "Taklifingiz qabul qilindi")
        seller = (NotificationType.OFFER_ACCEPTED, "Kelishuv tuzildi")
    for user_id, (type_, title) in ((deal.buyer_id, buyer), (deal.seller_id, seller)):
        notifier.create(user_id=user_id, type=type_, title=title, body=body, payload=payload)


def _notify_marked_sold(db: Session, deal: Deal) -> None:
    hours = settings.deal_auto_confirm_hours
    NotificationService(db).create(
        user_id=deal.buyer_id,
        type=NotificationType.DEAL_MARKED_SOLD,
        title="Sotuvchi «Sotildi» deb belgiladi",
        body=(
            f"«{_title(deal)}»: mahsulotni olgan bo'lsangiz, {hours} soat ichida tasdiqlang. "
            "Muammo bo'lsa shu muddatda shikoyat qoldiring — aks holda kelishuv "
            "avtomatik yakunlanadi."
        ),
        payload=_payload(deal, auto_confirm_hours=hours),
    )


def _notify_completed(db: Session, deal: Deal, *, auto: bool) -> None:
    lead = "Xaridor muddat ichida e'tiroz bildirmadi. " if auto else ""
    body = f"«{_title(deal)}». {lead}Endi bir-biringizga sharh qoldirishingiz mumkin."
    notifier = NotificationService(db)
    for user_id in (deal.buyer_id, deal.seller_id):
        notifier.create(
            user_id=user_id,
            type=NotificationType.DEAL_COMPLETED,
            title="Kelishuv yakunlandi",
            body=body,
            payload=_payload(deal, auto=auto),
        )


def _notify_cancelled(db: Session, deal: Deal, actor_id: int) -> None:
    """Bekor qilmagan tomon(lar)ga. Sabab — ro'yxatdagi matn (erkin matn emas)."""
    reason = deal.cancel_reason
    by_admin = actor_id not in {deal.buyer_id, deal.seller_id}
    prefix = "Moderator qarori bilan. " if by_admin else ""
    notifier = NotificationService(db)
    for user_id in (deal.buyer_id, deal.seller_id):
        if user_id == actor_id:
            continue
        notifier.create(
            user_id=user_id,
            type=NotificationType.DEAL_CANCELLED,
            title="Kelishuv bekor qilindi",
            body=f"«{_title(deal)}». {prefix}Sabab: {CANCEL_REASON_TEXT[reason]}.",
            payload=_payload(deal, reason=reason.value),
        )
