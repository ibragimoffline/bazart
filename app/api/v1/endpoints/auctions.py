from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.dependencies import CurrentActiveUser, CurrentUser, CurrentVerifiedUser, DbSession
from app.core.rate_limit import RateLimiter
from app.core.request_meta import client_ip, device_id
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.deal import Deal
from app.models.enums import AuctionStatus
from app.repositories.auction_repository import AuctionRepository
from app.repositories.bid_repository import BidRepository
from app.repositories.item_repository import ItemRepository
from app.schemas.auction import (
    AuctionCreate,
    AuctionPricingUpdate,
    AuctionRead,
    AuctionRelist,
    AuctionStatusUpdate,
)
from app.schemas.bid import BidCreate, BidRead
from app.schemas.deal import DealRead
from app.services.auction_service import AuctionService
from app.services.bid_service import BidService

router = APIRouter()
AuctionStatusQuery = Annotated[AuctionStatus | None, Query(alias="status")]
SkipQuery = Annotated[int, Query(ge=0)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]


@router.post("", response_model=AuctionRead, status_code=status.HTTP_201_CREATED)
def create_item_auction(
    payload: AuctionCreate,
    current_user: CurrentVerifiedUser,
    db: DbSession,
) -> Auction:
    item = ItemRepository(db).get(payload.item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your item")

    repository = AuctionRepository(db)
    if repository.item_has_auction(item.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item already has an auction",
        )
    return AuctionService(db).create_auction(current_user, item, payload)


@router.get("", response_model=list[AuctionRead])
def read_auctions(
    db: DbSession,
    status_filter: AuctionStatusQuery = AuctionStatus.ACTIVE,
    seller_id: Annotated[int | None, Query(ge=1)] = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 50,
) -> list[Auction]:
    return AuctionRepository(db).list(
        status=status_filter, seller_id=seller_id, skip=skip, limit=limit
    )


@router.get("/{auction_id}", response_model=AuctionRead)
def read_auction(auction_id: int, db: DbSession) -> Auction:
    auction = AuctionRepository(db).get(auction_id)
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    return auction


@router.patch("/{auction_id}/status", response_model=AuctionRead)
def set_auction_status(
    auction_id: int,
    payload: AuctionStatusUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> Auction:
    return AuctionService(db).set_status_by_seller(auction_id, current_user, payload.status)


@router.patch("/{auction_id}/pricing", response_model=AuctionRead)
def update_auction_pricing(
    auction_id: int,
    payload: AuctionPricingUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> Auction:
    """Narx rejimini (o'suvchi/pasayuvchi, buy-now, rezerv) boshlanishgacha o'zgartirish."""
    return AuctionService(db).update_pricing(auction_id, current_user, payload)


@router.post("/{auction_id}/close", response_model=AuctionRead)
def close_auction(
    auction_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> Auction:
    auction = AuctionRepository(db).get(auction_id)
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    if auction.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your auction")
    return AuctionService(db).close_auction(auction_id)


@router.post("/{auction_id}/second-chance/accept", response_model=AuctionRead)
def accept_second_chance(
    auction_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> Auction:
    """Sotuvchi second-chance taklifni qabul qiladi — eng yuqori bidderga sotadi."""
    return AuctionService(db).accept_second_chance(auction_id, current_user)


@router.post(
    "/{auction_id}/buy-now",
    response_model=AuctionRead,
    dependencies=[Depends(RateLimiter("bid", 60))],
)
def buy_now(
    auction_id: int, current_user: CurrentVerifiedUser, db: DbSession, request: Request
) -> Auction:
    """Lotni "hoziroq sotib olish" narxida sotib olish (faqat birinchi taklifgacha).

    Bloklangan foydalanuvchi sotib ololmaydi (CurrentActiveUser). Anti-fraud izi
    (ip/device/user-agent) oddiy bid kabi yoziladi.
    """
    ua = request.headers.get("user-agent")
    return AuctionService(db).buy_now(
        auction_id,
        current_user,
        ip=client_ip(request),
        device_id=device_id(request),
        user_agent=ua[:512] if ua else None,
    )


@router.post(
    "/{auction_id}/relist", response_model=AuctionRead, status_code=status.HTTP_201_CREATED
)
def relist_auction(
    auction_id: int,
    payload: AuctionRelist,
    current_user: CurrentVerifiedUser,
    db: DbSession,
) -> Auction:
    """Sotilmagan lotni yangi narx va muddat bilan qayta joylash (yangi auksion qaytadi).

    CurrentActiveUser: bloklangan sotuvchi relist orqali yangi e'lon ocholmaydi
    (POST /items ham shu tekshiruvni talab qiladi).
    """
    return AuctionService(db).relist(auction_id, current_user, payload)


@router.get("/{auction_id}/bids", response_model=list[BidRead])
def read_auction_bids(auction_id: int, db: DbSession, limit: LimitQuery = 50) -> list[Bid]:
    """Ochiq bid tarixi. Ism maskalangan (BidRead.bidder_display), proxy max
    (`max_amount`/`high_bidder_max`) sxemada YO'Q — oshkor bo'lmaydi."""
    if AuctionRepository(db).get(auction_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    return BidRepository(db).list_for_auction(auction_id, limit=limit)


@router.post(
    "/{auction_id}/bids",
    response_model=BidRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter("bid", 60))],
)
def create_bid(
    auction_id: int,
    payload: BidCreate,
    current_user: CurrentVerifiedUser,
    db: DbSession,
    request: Request,
) -> Bid:
    ua = request.headers.get("user-agent")
    idem = request.headers.get("idempotency-key")
    return BidService(db).place_bid(
        auction_id,
        current_user,
        payload,
        ip=client_ip(request),
        device_id=device_id(request),
        user_agent=ua[:512] if ua else None,
        idempotency_key=idem[:128] if idem else None,
    )


@router.post("/{auction_id}/next-offer/accept", response_model=DealRead)
def accept_next_offer(auction_id: int, current_user: CurrentVerifiedUser, db: DbSession) -> Deal:
    """Keyingi bidder sotuvchi taklifini qabul qiladi -> kelishuv (E2.10)."""
    return AuctionService(db).accept_next_offer(auction_id, current_user)
