from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import ItemStatus, ListingType
from app.models.item import Item, ItemImage
from app.models.user import User
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.translit import normalize_search


def _build_search_text(title: str | None, description: str | None) -> str | None:
    """title + description dan kanonik qidiruv matnini yasaydi.

    Lotin/kirill farqini yo'qotadi, shu bois "kompyuter" va "компьютер"
    bir xil satrga tushib, ILIKE bo'yicha bir-birini topadi.
    """
    parts = [part for part in (title, description) if part]
    if not parts:
        return None
    return normalize_search(" ".join(parts))


class ItemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, seller: User, payload: ItemCreate) -> Item:
        data = payload.model_dump()
        quantity = data.pop("quantity", 1)
        item = Item(
            seller_id=seller.id, quantity_total=quantity, quantity_available=quantity, **data
        )
        item.search_text = _build_search_text(data.get("title"), data.get("description"))
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list(
        self,
        *,
        q: str | None = None,
        category_id: int | None = None,
        seller_id: int | None = None,
        status: ItemStatus | None = None,
        location: str | None = None,
        region_id: int | None = None,
        district_id: int | None = None,
        listing_type: ListingType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Item]:
        statement = select(Item).order_by(Item.created_at.desc()).offset(skip).limit(limit)
        if q:
            # So'rovni ham indeksdagi kabi normallashtiramiz — lotin/kirill
            # farqi qidiruvga ta'sir qilmasin.
            normalized = normalize_search(q)
            if normalized:
                statement = statement.where(Item.search_text.ilike(f"%{normalized}%"))
        if category_id is not None:
            statement = statement.where(Item.category_id == category_id)
        if seller_id is not None:
            statement = statement.where(Item.seller_id == seller_id)
        if status is not None:
            statement = statement.where(Item.status == status)
        if region_id is not None:
            statement = statement.where(Item.region_id == region_id)
        if district_id is not None:
            statement = statement.where(Item.district_id == district_id)
        if listing_type is not None:
            statement = statement.where(Item.listing_type == listing_type)
        if location:
            # TODO: Replace this basic text match with geo-distance search.
            location_pattern = f"%{location}%"
            statement = statement.where(
                or_(
                    Item.location.ilike(location_pattern),
                    Item.item_location.ilike(location_pattern),
                )
            )
        return list(self.db.scalars(statement))

    def get(self, item_id: int) -> Item | None:
        return self.db.get(Item, item_id)

    def update(self, item: Item, payload: ItemUpdate) -> Item:
        data = payload.model_dump(exclude_unset=True)
        # Miqdor faqat qoralamada o'zgaradi (ItemService tekshiradi) — ikkala hisob birga.
        quantity = data.pop("quantity", None)
        if quantity is not None:
            item.quantity_total = quantity
            item.quantity_available = quantity
        for field, value in data.items():
            setattr(item, field, value)
        # title yoki description o'zgargan bo'lsa qidiruv matnini qayta yasaymiz.
        if "title" in data or "description" in data:
            item.search_text = _build_search_text(item.title, item.description)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_relist_of(self, item_id: int) -> Item | None:
        """Berilgan e'londan qayta joylangan e'lon (bo'lsa)."""
        return self.db.scalar(select(Item).where(Item.relisted_from_id == item_id))

    def clone_for_relist(
        self, source: Item, *, starting_price: int, reserve_price: int | None
    ) -> Item:
        """Sotilmagan e'lonning nusxasi — qayta joylash uchun. COMMIT QILMAYDI.

        Rasm fayllari ko'chirilmaydi: yangi yozuvlar o'sha URL'larga ishora
        qiladi (fayl o'chirish yo'li yo'q, shuning uchun ulashish xavfsiz).
        Narx yangi auksion bilan birga keladi; ko'rishlar soni noldan boshlanadi.
        """
        clone = Item(
            seller_id=source.seller_id,
            title=source.title,
            description=source.description,
            category_id=source.category_id,
            condition=source.condition,
            status=ItemStatus.DRAFT,
            images=list(source.images or []),
            location=source.location,
            item_location=source.item_location,
            year=source.year,
            equipment=source.equipment,
            defects=source.defects,
            video_url=source.video_url,
            region_id=source.region_id,
            district_id=source.district_id,
            search_text=source.search_text,
            starting_price=starting_price,
            reserve_price=reserve_price,
            relisted_from_id=source.id,
        )
        self.db.add(clone)
        self.db.flush()
        for image in source.item_images:
            self.db.add(
                ItemImage(item_id=clone.id, image_url=image.image_url, is_primary=image.is_primary)
            )
        self.db.flush()
        return clone

    def mark_cancelled(self, item: Item) -> Item:
        item.status = ItemStatus.CANCELLED
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def add_image(self, item: Item, image_url: str, *, is_primary: bool = False) -> ItemImage:
        if is_primary:
            for image in item.item_images:
                image.is_primary = False
                self.db.add(image)

        item_image = ItemImage(item_id=item.id, image_url=image_url, is_primary=is_primary)
        item.images = [*item.images, image_url]
        self.db.add(item)
        self.db.add(item_image)
        self.db.commit()
        self.db.refresh(item_image)
        return item_image
