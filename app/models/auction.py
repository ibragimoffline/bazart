from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AuctionStatus, PricingMode
from app.money import TIYIN_PER_SOUM, Tiyin


class Auction(Base):
    __tablename__ = "auctions"

    # Sweeper (close_due_auctions) `status == ACTIVE AND end_time <= now`
    # bo'yicha qidiradi — kompozit index shu so'rovni tez qiladi.
    __table_args__ = (
        Index("ix_auctions_status_end_time", "status", "end_time"),
        # Pasayuvchi auksionda qadam, oraliq va pastki chegara (reserve_price) majburiy —
        # aks holda narx nolga (yoki manfiyga) tushib, tovar tekinga ketardi.
        CheckConstraint(
            "pricing_mode = 'ASCENDING' OR (price_decrement > 0 "
            "AND price_drop_interval_minutes > 0 AND reserve_price IS NOT NULL)",
            name="ck_auctions_descending_config",
        ),
        # Golland zaxirasi (sotuvchi roziligi) faqat o'suvchi auksionda ma'noga ega.
        CheckConstraint(
            "dutch_fallback_floor IS NULL OR (pricing_mode = 'ASCENDING' "
            "AND dutch_fallback_floor > 0)",
            name="ck_auctions_dutch_fallback",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), unique=True, nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    # Muddat: 3/5/7 kun (mahsulotning asosiy qoidasi — majburiy deadline).
    # Nullable: to'g'ridan-to'g'ri end_time bilan yaratilgan auksionlar uchun
    # (orqaga moslik). duration_days berilsa end_time = start_time + kun.
    duration_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Anti-sniping necha marta muddatni uzaytirgani — cheksiz cho'zilmasin.
    extension_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[AuctionStatus] = mapped_column(
        SqlEnum(AuctionStatus, name="auction_status"),
        default=AuctionStatus.SCHEDULED,
        index=True,
        nullable=False,
    )
    # Pul — tiyinda (BIGINT). Batafsil: app/money/
    starting_price: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    current_price: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    # Default 1 so'm = 100 tiyin (ilgari Numeric'da default=1 so'm edi).
    minimum_bid_increment: Mapped[Tiyin] = mapped_column(
        BigInteger, default=TIYIN_PER_SOUM, nullable=False
    )
    reserve_price: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    highest_bidder_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True, nullable=True
    )
    # Proxy bidding siri: joriy leader to'lashga tayyor MAKSIMAL summa (tiyin).
    # HECH QACHON API'da oshkor bo'lmaydi (AuctionRead'da yo'q) — oshkor bo'lsa
    # raqib uni bir qadam bilan yengib o'tadi.
    high_bidder_max: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    winning_bid_id: Mapped[int | None] = mapped_column(
        ForeignKey("bids.id", name="fk_auctions_winning_bid_id_bids", use_alter=True),
        nullable=True,
    )
    # Anti-sniping end_time'ni surganda ORIGINAL muddat shu yerda saqlanadi —
    # "qancha cho'zildi" auditi va ko'rsatish uchun. Auksion aktivlashganda/
    # yaratilganda o'rnatiladi.
    original_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Auksion amalda yopilgan (g'olib aniqlangan) vaqt.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Denormalizatsiya — har bidda qulf ostida yangilanadi. Ro'yxat/karta
    # ko'rsatishda har safar COUNT(*) qilmaslik uchun.
    bid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unique_bidder_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # "Hoziroq sotib olish" narxi (tiyin). None = buy-now o'chiq.
    buy_now_price: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    # Narx yo'nalishi. DESCENDING: narx `price_drop_interval_minutes` da bir
    # `price_decrement` ga pasayadi, `reserve_price` dan pastga tushmaydi. Joriy narx
    # BAZADA SAQLANMAYDI — vaqtdan hisoblanadi (`services/price_schedule.py`);
    # `current_price` faqat sotilganda (sotuv narxi) yoziladi.
    pricing_mode: Mapped[PricingMode] = mapped_column(
        SqlEnum(PricingMode, name="pricing_mode"),
        default=PricingMode.ASCENDING,
        server_default=PricingMode.ASCENDING.name,
        nullable=False,
    )
    price_decrement: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    price_drop_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "Narx tushdi" xabari oxirgi marta qaysi narxda yuborilgan (NULL — hali yuborilmagan).
    last_price_alert: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    # Sotuvchining OLDINDAN roziligi: taklifsiz tugasa lot 3 kunlik pasayuvchi auksionga
    # avtomatik o'tadi; qiymat — o'sha bosqichning pastki chegarasi (tiyin). NULL = rozilik
    # yo'q. Qiymati javobda oshkor bo'lmaydi (faqat `dutch_fallback_enabled`).
    dutch_fallback_floor: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    # Shu auksion taklifsiz tugab, davom etgan pasayuvchi auksion (UNIQUE — bir marta).
    continued_as_auction_id: Mapped[int | None] = mapped_column(
        ForeignKey("auctions.id", name="fk_auctions_continued_as_auction_id"),
        unique=True,
        nullable=True,
    )
    # Second-chance offer: reserve bajarilmaganda sotuvchiga eng yuqori
    # bidderga sotish taklifi beriladi. offered_at = taklif berilgan vaqt,
    # expires_at = taklif amal qilish muddati (24 soat).
    second_chance_offered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    second_chance_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # "Tugashiga oz qoldi" eslatmasi yuborilgan vaqt. NULL = hali yuborilmagan;
    # eslatma auksionga BIR MARTA ketadi (anti-sniping uzaytirsa ham takrorlanmaydi).
    ending_soon_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    item = relationship("Item", back_populates="auction")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="auctions")
    highest_bidder = relationship("User", foreign_keys=[highest_bidder_id])
    winner = relationship("User", foreign_keys=[winner_id], back_populates="won_auctions")
    bids = relationship(
        "Bid",
        back_populates="auction",
        cascade="all, delete-orphan",
        foreign_keys="Bid.auction_id",
    )
    winning_bid = relationship("Bid", foreign_keys=[winning_bid_id], post_update=True)
    deal = relationship("Deal", back_populates="auction", uselist=False)
