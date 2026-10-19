from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import DealCancelReason, DealStatus
from app.money import Tiyin


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        # Deal manbai — yo auksion g'olibi, yo qabul qilingan taklif (aynan bittasi).
        CheckConstraint(
            "(auction_id IS NULL) <> (offer_id IS NULL)", name="ck_deals_single_source"
        ),
        CheckConstraint("quantity >= 1", name="ck_deals_quantity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    auction_id: Mapped[int | None] = mapped_column(
        ForeignKey("auctions.id"), unique=True, nullable=True
    )
    offer_id: Mapped[int | None] = mapped_column(
        ForeignKey("offers.id"), unique=True, nullable=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True, nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    # Pul — tiyinda (BIGINT). Batafsil: app/money/
    # final_price — JAMI (quantity x unit_price).
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    unit_price: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    final_price: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    status: Mapped[DealStatus] = mapped_column(
        SqlEnum(DealStatus, name="deal_status"),
        default=DealStatus.AGREED,
        index=True,
        nullable=False,
    )
    # Kontaktlar birinchi marta ochilgan vaqt (agreed ga kirganda). Ochilgan kontakt qayta
    # yashirilmaydi; 48 soatlik bog'lanish oynasi ham shundan hisoblanadi.
    contacts_revealed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Sotuvchi "Sotildi" belgiladi — 72 soatlik avto-tasdiq shundan hisoblanadi.
    seller_marked_sold_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    buyer_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    cancel_reason: Mapped[DealCancelReason | None] = mapped_column(
        SqlEnum(DealCancelReason, name="deal_cancel_reason"), nullable=True
    )
    # Bekor qilishda aybdor tomon (sababdan) — hisoblagich shunga yoziladi.
    at_fault_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    auction = relationship("Auction", back_populates="deal")
    offer = relationship("Offer", back_populates="deal")
    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="deals_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="deals_as_seller")
    item = relationship("Item")
