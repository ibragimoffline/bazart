from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auction import Auction
from app.models.deal import Deal
from app.models.enums import DealCancelReason, DealStatus, ItemStatus, is_admin
from app.models.offer import Offer
from app.models.user import User
from app.money import Tiyin, calc_line_total
from app.repositories.deal_repository import DealRepository
from app.repositories.offer_repository import OfferRepository
from app.services.deal_state import InvalidDealTransition, assert_deal_transition


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
        return self.deals.add(deal)

    def create_for_winning_auction(self, auction: Auction) -> Deal | None:
        """Auksion g'olibi (yopilish, buy-now, tushuvchi narx, keyingi bidder). Idempotent."""
        if auction.winner_id is None or auction.winning_bid is None:
            return None
        existing = self.deals.get_by_auction_id(auction.id)
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
        deal = self.deals.get(deal_id)
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        if is_admin(user.role) or user.id in {deal.buyer_id, deal.seller_id}:
            return deal
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your deal")

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
        if deal.seller_marked_sold_at is None:
            deal.seller_marked_sold_at = datetime.now(UTC)
        if deal.buyer_confirmed_at is not None:
            self._transition(deal, DealStatus.COMPLETED)
            deal.completed_at = datetime.now(UTC)
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
            self._transition(deal, DealStatus.COMPLETED)
            deal.completed_at = datetime.now(UTC)
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
        deal.cancelled_by_id = actor.id
        deal.cancel_reason = reason
        deal.at_fault_id = at_fault_for(deal, actor.id, reason)
        self._restore_stock(deal)
        return self._save(deal)

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
