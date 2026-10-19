from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.money import Tiyin


class NextBidderOffer(Base):
    """Keyingi bidderga taklif (Faza E2.10, docs/DEALS.md §6).

    G'olib javob bermay kelishuv bekor bo'lgach sotuvchi keyingi bidderga uning bid narxida
    24 soatlik taklif yuboradi. Har taklif shu jadvalda qoladi: kim taklif olganini bilish
    uchun bid tarixi o'zgartirilmaydi. UNIQUE (auction_id, bidder_id): bir bidder bir
    auksionda ko'pi bilan bitta taklif oladi — javob bermagan bidderga ikkinchi marta yo'q.

    Ochiq taklif: `accepted_at`, `closed_at` bo'sh va `expires_at` kelmagan. Muddat o'tishi
    vaqtdan hisoblanadi (alohida fon vazifasi shart emas). `closed_at` — qayta joylash yoki
    rad etish yopgan vaqt (E3.6).
    """

    __tablename__ = "next_bidder_offers"
    __table_args__ = (
        UniqueConstraint("auction_id", "bidder_id", name="uq_next_bidder_offers_auction_bidder"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"), index=True, nullable=False)
    bidder_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    bid_id: Mapped[int] = mapped_column(ForeignKey("bids.id"), nullable=False)
    # Taklif narxi — o'sha bidderning bid summasi (tiyin).
    amount: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    offered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id"), nullable=True)

    auction = relationship("Auction")
    bid = relationship("Bid")

    def is_open(self, now: datetime) -> bool:
        expires = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=UTC)
        return self.accepted_at is None and self.closed_at is None and expires > now
