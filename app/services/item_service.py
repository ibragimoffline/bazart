from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AuctionStatus, ItemStatus, ListingType, is_admin
from app.models.item import Item, ItemImage
from app.models.user import User
from app.repositories.item_repository import ItemRepository
from app.repositories.region_repository import RegionRepository
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.auction_service import AuctionService
from app.services.offer_service import OfferService
from app.services.storage_service import StorageService


class ItemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ItemRepository(db)
        self.regions = RegionRepository(db)
        self.storage = StorageService()

    def create_item(self, seller: User, payload: ItemCreate) -> Item:
        self._validate_location(payload.region_id, payload.district_id)
        return self.repository.create(seller, payload)

    def get_item_or_404(self, item_id: int) -> Item:
        item = self.repository.get(item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item

    def update_item(self, item_id: int, payload: ItemUpdate, actor: User) -> Item:
        item = self.get_item_or_404(item_id)
        self._ensure_can_manage_item(item, actor)
        # Qisman yangilash: berilmagan maydon mavjud qiymat bilan birga tekshiriladi.
        fields = payload.model_fields_set
        region_id = payload.region_id if "region_id" in fields else item.region_id
        district_id = payload.district_id if "district_id" in fields else item.district_id
        self._validate_location(region_id, district_id)
        if "quantity" in fields and payload.quantity is not None:
            # E'lon qilingach miqdor o'zgarmaydi: ochiq takliflar va tuzilgan bitimlar
            # shu zaxiraga tayanadi (aks holda sotilgan donalar "qaytib kelardi").
            if item.listing_type is not None or item.status != ItemStatus.DRAFT:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Quantity can only be changed before the listing is published",
                )
        return self.repository.update(item, payload)

    def cancel_item(self, item_id: int, actor: User) -> Item:
        """E'lonni bekor qiladi (sotuvchi "e'lonni olib tashlash").

        Ilgari faqat item.status yozilardi — jonli auksion esa ishlashda
        davom etar, bid qabul qilar va yopilganda bekor qilingan tovarga
        deal yaratardi. Endi jonli auksion bo'lsa bekor qilish auksion
        oqimi orqali o'tadi: qator FOR UPDATE bilan qulflanadi, state machine
        tekshiriladi va bidli auksion bekor qilinmaydi (bidlar kuymaydi).
        Yakunlangan auksion yoki sotilgan tovar bekor qilinmaydi.
        """
        item = self.get_item_or_404(item_id)
        self._ensure_can_manage_item(item, actor)
        if item.status == ItemStatus.CANCELLED:
            return item
        if item.status == ItemStatus.SOLD:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Sold item cannot be cancelled"
            )

        if item.listing_type == ListingType.OFFER:
            return OfferService(self.db).cancel_listing(item.id)

        auction = item.auction
        if auction is not None:
            if auction.status in (AuctionStatus.SCHEDULED, AuctionStatus.ACTIVE):
                auctions = AuctionService(self.db)
                if is_admin(actor.role) and actor.id != item.seller_id:
                    auctions.cancel_as_admin(auction.id)
                else:
                    auctions.set_status_by_seller(auction.id, actor, AuctionStatus.CANCELLED)
                self.db.refresh(item)
                return item
            if auction.status != AuctionStatus.CANCELLED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Auction has already finished; listing cannot be cancelled",
                )
        return self.repository.mark_cancelled(item)

    def upload_image(
        self,
        item_id: int,
        file: UploadFile,
        actor: User,
        *,
        is_primary: bool = False,
    ) -> ItemImage:
        item = self.get_item_or_404(item_id)
        self._ensure_can_manage_item(item, actor)
        # Har lotdagi rasm sonini cheklaymiz — storage suiiste'moli va
        # og'ir ro'yxat sahifasining oldini oladi.
        if len(item.item_images) >= settings.max_images_per_item:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rasm limiti oshib ketdi (maks {settings.max_images_per_item})",
            )
        image_url = self.storage.save_upload(file, folder="items")
        return self.repository.add_image(item, image_url, is_primary=is_primary)

    def _validate_location(self, region_id: int | None, district_id: int | None) -> None:
        """Tuman tanlangan viloyatga tegishli bo'lishi shart.

        Aks holda lot ziddiyatli manzil bilan saqlanib, hudud filtri bo'yicha
        noto'g'ri natija beradi (yoki boshqa viloyat qidiruvida chiqadi).
        """
        if region_id is not None and self.regions.get_region(region_id) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown region")
        if district_id is None:
            return
        district = self.regions.get_district(district_id)
        if district is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown district")
        if district.region_id != region_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="District does not belong to the selected region",
            )

    def _ensure_can_manage_item(self, item: Item, actor: User) -> None:
        if is_admin(actor.role):
            return
        if item.seller_id != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item")
