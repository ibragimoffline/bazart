from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.core.dependencies import CurrentActiveUser, CurrentUser, CurrentVerifiedUser, DbSession
from app.core.rate_limit import RateLimiter
from app.models.enums import ItemStatus, ListingType
from app.models.item import Item
from app.models.offer import Offer
from app.repositories.item_repository import ItemRepository
from app.schemas.item import ItemCreate, ItemImageUploadRead, ItemPublish, ItemRead, ItemUpdate
from app.schemas.offer import OfferCreate, OfferRead
from app.services.item_service import ItemService
from app.services.offer_service import OfferService

router = APIRouter()
SkipQuery = Annotated[int, Query(ge=0)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
CategoryQuery = Annotated[int | None, Query()]
SellerQuery = Annotated[int | None, Query()]
StatusQuery = Annotated[ItemStatus | None, Query(alias="status")]
LocationQuery = Annotated[str | None, Query(max_length=160)]
SearchQuery = Annotated[str | None, Query(max_length=160)]
RegionQuery = Annotated[int | None, Query()]
DistrictQuery = Annotated[int | None, Query()]
ListingTypeQuery = Annotated[ListingType | None, Query()]
UploadImage = Annotated[UploadFile, File()]
PrimaryImageForm = Annotated[bool, Form()]


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_listing(payload: ItemCreate, current_user: CurrentVerifiedUser, db: DbSession) -> Item:
    return ItemService(db).create_item(current_user, payload)


@router.get("", response_model=list[ItemRead])
def read_listings(
    db: DbSession,
    q: SearchQuery = None,
    category_id: CategoryQuery = None,
    seller_id: SellerQuery = None,
    status_filter: StatusQuery = None,
    location: LocationQuery = None,
    region_id: RegionQuery = None,
    district_id: DistrictQuery = None,
    listing_type: ListingTypeQuery = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 50,
) -> list[Item]:
    return ItemRepository(db).list(
        q=q,
        category_id=category_id,
        seller_id=seller_id,
        status=status_filter,
        location=location,
        region_id=region_id,
        district_id=district_id,
        listing_type=listing_type,
        skip=skip,
        limit=limit,
    )


@router.get("/{item_id}", response_model=ItemRead)
def read_listing(item_id: int, db: DbSession) -> Item:
    return ItemService(db).get_item_or_404(item_id)


@router.patch("/{item_id}", response_model=ItemRead)
def update_listing(
    item_id: int,
    payload: ItemUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> Item:
    return ItemService(db).update_item(item_id, payload, current_user)


@router.delete("/{item_id}", response_model=ItemRead)
def delete_listing(
    item_id: int,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> Item:
    return ItemService(db).cancel_item(item_id, current_user)


@router.post(
    "/{item_id}/images", response_model=ItemImageUploadRead, status_code=status.HTTP_201_CREATED
)
def upload_item_image(
    item_id: int,
    file: UploadImage,
    current_user: CurrentActiveUser,
    db: DbSession,
    is_primary: PrimaryImageForm = False,
) -> ItemImageUploadRead:
    image = ItemService(db).upload_image(item_id, file, current_user, is_primary=is_primary)
    return ItemImageUploadRead(image=image)


@router.post("/{item_id}/publish", response_model=ItemRead)
def publish_listing(
    item_id: int, payload: ItemPublish, current_user: CurrentVerifiedUser, db: DbSession
) -> Item:
    """Qoralamani taklifli e'lon qiladi (yoki muddati o'tganini qayta ochadi)."""
    return OfferService(db).publish(item_id, current_user, payload)


@router.post(
    "/{item_id}/offers",
    response_model=OfferRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter("bid", 60))],
)
def create_offer(
    item_id: int, payload: OfferCreate, current_user: CurrentVerifiedUser, db: DbSession
) -> Offer:
    """Xaridor narx va miqdor taklif qiladi (istalgan musbat dona narxi)."""
    return OfferService(db).make_offer(item_id, current_user, payload)


@router.get("/{item_id}/offers", response_model=list[OfferRead])
def read_item_offers(item_id: int, current_user: CurrentUser, db: DbSession) -> list[Offer]:
    """Sotuvchi — barcha takliflar; boshqa foydalanuvchi — faqat o'z takliflari."""
    return OfferService(db).list_for_item(item_id, current_user)
