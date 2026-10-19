"""Narx taklifi (offer) — taklifli e'londa xaridor va sotuvchi o'rtasidagi muzokara.

Joriy shartlar (`quantity`, `unit_price`) Offer qatorida; har harakat (taklif,
qarshi taklif, qabul, rad, qaytarib olish, muddat o'tishi) `OfferEvent` tarixiga
yoziladi. `awaiting` — kimning javobi kutilmoqda: faqat o'sha tomon qabul qiladi,
rad etadi yoki qarshi taklif beradi (o'z taklifini o'zi qabul qila olmaydi).

Pul — tiyinda (BIGINT), DONA uchun. Jami = quantity * unit_price (`calc_line_total`).
"""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import OfferParty, OfferStatus
from app.money import Tiyin


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_offers_quantity_positive"),
        CheckConstraint("unit_price > 0", name="ck_offers_unit_price_positive"),
        # Bitta xaridorning bitta e'londa faqat BITTA ochiq taklifi bo'ladi —
        # shartni o'zgartirish uchun qarshi taklif yoki qaytarib olish ishlatiladi.
        # Enum Postgres'da NOMI bilan saqlanadi ('PENDING').
        Index(
            "uq_offers_open_per_buyer",
            "item_id",
            "buyer_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True, nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        SqlEnum(OfferStatus, name="offer_status"),
        default=OfferStatus.PENDING,
        index=True,
        nullable=False,
    )
    awaiting: Mapped[OfferParty] = mapped_column(
        SqlEnum(OfferParty, name="offer_party"), nullable=False
    )
    # Javobsiz qolsa shu vaqtda muddati o'tadi (har qarshi taklifda yangilanadi).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    item = relationship("Item", back_populates="offers")
    buyer = relationship("User", foreign_keys=[buyer_id])
    seller = relationship("User", foreign_keys=[seller_id])
    events = relationship(
        "OfferEvent",
        back_populates="offer",
        cascade="all, delete-orphan",
        order_by="OfferEvent.id",
    )
    order = relationship("Order", back_populates="offer", uselist=False)

    @property
    def total_price(self) -> Tiyin:
        from app.money import calc_line_total

        return calc_line_total(self.unit_price, self.quantity)


class OfferEvent(Base):
    """Muzokara tarixi: kim, nima qildi va qaysi shartlar bilan."""

    __tablename__ = "offer_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    offer_id: Mapped[int] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # NULL actor — tizim (muddat o'tishi, zaxira tugashi).
    actor: Mapped[OfferParty | None] = mapped_column(
        SqlEnum(OfferParty, name="offer_party"), nullable=True
    )
    # "offer" | "counter" | "accept" | "reject" | "withdraw" | "expire" | "sold_out" | "cancel"
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[int | None] = mapped_column(nullable=True)
    unit_price: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    offer = relationship("Offer", back_populates="events")
