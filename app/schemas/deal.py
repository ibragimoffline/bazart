from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DealCancelReason, DealStatus
from app.money.fields import TiyinAmount


class DealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    auction_id: int | None
    offer_id: int | None = None
    item_id: int
    buyer_id: int
    seller_id: int
    quantity: int = 1
    # Dona narxi va jami (final_price = quantity x unit_price), tiyinda.
    unit_price: TiyinAmount
    final_price: TiyinAmount
    status: DealStatus
    seller_marked_sold_at: datetime | None = None
    buyer_confirmed_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancelled_by_id: int | None = None
    cancel_reason: DealCancelReason | None = None
    at_fault_id: int | None = None
    created_at: datetime
    updated_at: datetime


class DealContact(BaseModel):
    """Ikkinchi tomon kontakti — faqat kelishuv ishtirokchisiga, kontaktlar ochilgandan keyin.

    `phone` faqat OTP bilan tasdiqlangan bo'lsa (raqam o'zgarsa tasdiq bekor bo'ladi va bu
    yerda None qaytadi — tasdiqlanmagan raqam ishonch belgisi sifatida ko'rsatilmaydi).
    """

    user_id: int
    full_name: str | None
    phone: str | None
    telegram_username: str | None


class DealDetail(DealRead):
    """GET /deals/{id}: kelishuv + (ishtirokchiga) ikkinchi tomon kontakti."""

    counterparty: DealContact | None = None


class NextBidderOffer(BaseModel):
    """Keyingi bidderga yuborilgan taklif (E2.10). Bidder kimligi sotuvchiga ham maskalangan:
    kontakt faqat kelishuvdan keyin."""

    model_config = ConfigDict(from_attributes=True)

    auction_id: int
    amount: TiyinAmount
    expires_at: datetime


class DealCancel(BaseModel):
    reason: DealCancelReason
