from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ItemStatus, OfferParty, OfferStatus
from app.money.fields import TiyinAmount
from app.schemas.bid import mask_name
from app.schemas.item import MAX_QUANTITY


class OfferCreate(BaseModel):
    """Xaridor taklifi: miqdor va DONA narxi. Har qanday musbat narx qabul qilinadi —
    mo'ljal narxdan past ham, yuqori ham; boshqa takliflardan oshishi shart emas."""

    quantity: int = Field(ge=1, le=MAX_QUANTITY)
    # Pul tiyinda, JSON'da string: {"unit_price": "1500000"}
    unit_price: TiyinAmount = Field(gt=0)
    message: str | None = Field(default=None, max_length=500)


class OfferCounter(OfferCreate):
    """Qarshi taklif: javob navbati kimda bo'lsa, o'sha yangi shartlarni beradi."""


class OfferEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: OfferParty | None
    action: str
    quantity: int | None
    unit_price: TiyinAmount | None
    message: str | None
    created_at: datetime


class OfferItemBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    images: list[str] = Field(default_factory=list)
    # Qarshi taklif shakli uchun: mo'ljal narx (dona) va hozirgi zaxira.
    starting_price: TiyinAmount
    quantity_available: int
    status: ItemStatus


class OfferRead(BaseModel):
    """Taklif — faqat ikki ishtirokchiga (va adminga) ko'rinadi."""

    id: int
    item_id: int
    item: OfferItemBrief | None = None
    buyer_id: int
    seller_id: int
    # Xaridor ismi qabul qilinguncha maskalangan (bid tarixidagi kabi).
    buyer_display: str
    quantity: int
    unit_price: TiyinAmount
    total_price: TiyinAmount
    status: OfferStatus
    awaiting: OfferParty
    expires_at: datetime
    deal_id: int | None = None
    events: list[OfferEventRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _from_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        buyer = getattr(data, "buyer", None)
        full_name = getattr(buyer, "full_name", None)
        accepted = data.status == OfferStatus.ACCEPTED
        deal = getattr(data, "deal", None)
        return {
            "id": data.id,
            "item_id": data.item_id,
            "item": data.item,
            "buyer_id": data.buyer_id,
            "seller_id": data.seller_id,
            "buyer_display": (full_name or "Xaridor") if accepted else mask_name(full_name),
            "quantity": data.quantity,
            "unit_price": data.unit_price,
            "total_price": data.total_price,
            "status": data.status,
            "awaiting": data.awaiting,
            "expires_at": data.expires_at,
            "deal_id": deal.id if deal is not None else None,
            "events": list(data.events),
            "created_at": data.created_at,
            "updated_at": data.updated_at,
        }
