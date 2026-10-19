from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ItemStatus, ListingType, OfferParty, OfferStatus
from app.models.item import Item
from app.models.offer import Offer, OfferEvent


def _load_options() -> tuple:
    """Eager-load (tarix, e'lon, xaridor). Import paytida EMAS — mapper'lar hali
    to'liq konfiguratsiya qilinmagan bo'lishi mumkin."""
    return (selectinload(Offer.events), selectinload(Offer.item), selectinload(Offer.buyer))


class OfferRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, offer_id: int) -> Offer | None:
        return self.db.get(Offer, offer_id)

    def get_for_update(self, offer_id: int) -> Offer | None:
        """Taklif qatorini qulflaydi — bitta taklifga parallel javoblar navbatma-navbat."""
        statement = select(Offer).where(Offer.id == offer_id).with_for_update()
        return self.db.scalars(statement).one_or_none()

    def lock_item(self, item_id: int) -> Item | None:
        """E'lon qatorini qulflaydi (SELECT ... FOR UPDATE).

        Zaxira (quantity_available) faqat shu qulf ostida o'zgaradi: ikki sotuvchi
        oynasidan (yoki sotuvchi + xaridor) bir vaqtda qabul qilish navbatma-navbat
        bajariladi va oxirgi dona ikki marta sotilmaydi.
        """
        statement = select(Item).where(Item.id == item_id).with_for_update()
        return self.db.scalars(statement).one_or_none()

    def take_stock(self, item_id: int, quantity: int) -> int | None:
        """Zaxiradan ATOMIK ayiradi; yetmasa None (hech narsa o'zgarmaydi).

        Shartli UPDATE (`... WHERE quantity_available >= :q`): Postgres shartni eng
        so'nggi tasdiqlangan qatorga qayta tekshiradi — "o'qi -> ayir -> yoz" lost
        update'i bo'lmaydi. FOR UPDATE qulfi bilan birga ikki qavat himoya: qulf
        olib tashlansa ham ortiqcha sotuv (oversell) yuz bermaydi.
        """
        statement = (
            update(Item)
            .where(Item.id == item_id, Item.quantity_available >= quantity)
            .values(quantity_available=Item.quantity_available - quantity)
            .returning(Item.quantity_available)
            .execution_options(synchronize_session=False)
        )
        return self.db.scalar(statement)

    def get_open_for_buyer(self, item_id: int, buyer_id: int) -> Offer | None:
        statement = select(Offer).where(
            Offer.item_id == item_id,
            Offer.buyer_id == buyer_id,
            Offer.status == OfferStatus.PENDING,
        )
        return self.db.scalar(statement)

    def list_open_for_item(self, item_id: int, *, exclude_id: int | None = None) -> list[Offer]:
        statement = select(Offer).where(
            Offer.item_id == item_id, Offer.status == OfferStatus.PENDING
        )
        if exclude_id is not None:
            statement = statement.where(Offer.id != exclude_id)
        return list(self.db.scalars(statement))

    def list_for_item(self, item_id: int, *, buyer_id: int | None = None) -> list[Offer]:
        statement = (
            select(Offer)
            .where(Offer.item_id == item_id)
            .options(*_load_options())
            .order_by(Offer.created_at.desc())
        )
        if buyer_id is not None:
            statement = statement.where(Offer.buyer_id == buyer_id)
        return list(self.db.scalars(statement))

    def list_for_user(
        self,
        user_id: int,
        role: OfferParty,
        *,
        status: OfferStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Offer]:
        column = Offer.buyer_id if role == OfferParty.BUYER else Offer.seller_id
        statement = (
            select(Offer)
            .where(column == user_id)
            .options(*_load_options())
            .order_by(Offer.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status is not None:
            statement = statement.where(Offer.status == status)
        return list(self.db.scalars(statement))

    def list_due_offer_ids(self, now: datetime) -> list[int]:
        statement = select(Offer.id).where(
            Offer.status == OfferStatus.PENDING, Offer.expires_at <= now
        )
        return list(self.db.scalars(statement))

    def list_due_listing_ids(self, now: datetime) -> list[int]:
        statement = select(Item.id).where(
            Item.listing_type == ListingType.OFFER,
            Item.status == ItemStatus.ACTIVE,
            Item.listing_ends_at <= now,
        )
        return list(self.db.scalars(statement))

    def add_event(
        self,
        offer: Offer,
        *,
        actor: OfferParty | None,
        action: str,
        quantity: int | None = None,
        unit_price: int | None = None,
        message: str | None = None,
    ) -> OfferEvent:
        event = OfferEvent(
            offer=offer,
            actor=actor,
            action=action,
            quantity=quantity,
            unit_price=unit_price,
            message=message,
        )
        self.db.add(event)
        return event
