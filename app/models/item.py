from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ItemCondition, ItemStatus, ListingType
from app.money import Tiyin


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("relisted_from_id", name="uq_items_relisted_from_id"),
        # Diapazon kafolati (manfiy zaxira yo'q). Lost update'dan himoya — bu EMAS:
        # u OfferService.accept'dagi FOR UPDATE + shartli UPDATE (take_stock)da.
        CheckConstraint(
            "quantity_available >= 0 AND quantity_available <= quantity_total",
            name="ck_items_quantity_available_range",
        ),
        CheckConstraint("quantity_total >= 1", name="ck_items_quantity_total_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), index=True)
    condition: Mapped[ItemCondition] = mapped_column(
        SqlEnum(ItemCondition, name="item_condition"),
        default=ItemCondition.USED,
        nullable=False,
    )
    status: Mapped[ItemStatus] = mapped_column(
        SqlEnum(ItemStatus, name="item_status"),
        default=ItemStatus.DRAFT,
        nullable=False,
    )
    images: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    item_location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Domen boyitish: ishlab chiqarish yili, komplektatsiya, nuqsonlar, video.
    year: Mapped[int | None] = mapped_column(nullable=True)
    equipment: Mapped[str | None] = mapped_column(Text, nullable=True)
    defects: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Hudud/tuman — jadvallar app/models/region.py da (boshqa agent).
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"), index=True)
    view_count: Mapped[int] = mapped_column(default=0, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Normallashtirilgan qidiruv matni (lotin kanon). ILIKE bo'yicha qidiriladi.
    search_text: Mapped[str | None] = mapped_column(Text, index=True, nullable=True)
    # Pul — tiyinda (BIGINT). Batafsil: app/money/
    # Taklifli e'londa starting_price = sotuvchining mo'ljal narxi, BIR DONA uchun
    # (majburiy chegara emas — xaridor pastroq yoki yuqoriroq taklif qila oladi).
    starting_price: Mapped[Tiyin] = mapped_column(BigInteger, nullable=False)
    reserve_price: Mapped[Tiyin | None] = mapped_column(BigInteger, nullable=True)
    # Sotilmagan lot qayta joylanganda yangi e'lon eskisiga ishora qiladi.
    # UNIQUE: bitta e'lon faqat bir marta qayta joylanadi (parallel so'rov ham
    # ikki nusxa yarata olmaydi). Har item'da faqat bitta auksion bo'lgani uchun
    # qayta joylash = yangi item + yangi auksion.
    relisted_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("items.id", name="fk_items_relisted_from_id_items"), nullable=True
    )
    # Sotish rejimi: e'lon qilinganda belgilanadi (qoralamada NULL).
    listing_type: Mapped[ListingType | None] = mapped_column(
        SqlEnum(ListingType, name="listing_type"), index=True, nullable=True
    )
    # Zaxira: jami dona va hali sotilmagan (qabul qilingan takliflar ayirilgan) dona.
    # Auksion e'loni har doim 1 dona.
    quantity_total: Mapped[int] = mapped_column(default=1, nullable=False)
    quantity_available: Mapped[int] = mapped_column(default=1, nullable=False)
    # Taklifli e'lon muddati (majburiy 3/5/7 kun). Auksionda muddat auction.end_time'da.
    listing_duration_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    listing_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    seller = relationship("User", back_populates="items")
    category = relationship("Category", back_populates="items")
    auction = relationship("Auction", back_populates="item", uselist=False)
    offers = relationship("Offer", back_populates="item", order_by="Offer.created_at.desc()")
    item_images = relationship(
        "ItemImage",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ItemImage.created_at",
    )


class ItemImage(Base):
    __tablename__ = "item_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)

    item = relationship("Item", back_populates="item_images")
