from fastapi import APIRouter, Depends, Request, status

from app.core.dependencies import CurrentAdminUser, CurrentUser, CurrentVerifiedUser, DbSession
from app.core.rate_limit import RateLimiter
from app.core.request_meta import client_ip, device_id
from app.models.bid import Bid
from app.schemas.bid import BidCreate, BidInvalidate, BidRead
from app.services.bid_service import BidService

router = APIRouter()


def _user_agent(request: Request) -> str | None:
    """So'rovdan User-Agent sarlavhasini oladi (audit izi uchun, ixtiyoriy)."""
    value = request.headers.get("user-agent")
    return value[:512] if value else None


def _idempotency_key(request: Request) -> str | None:
    """Idempotency-Key sarlavhasi — takroriy bid so'rovini bir xil deb belgilaydi."""
    value = request.headers.get("idempotency-key")
    return value[:128] if value else None


@router.post(
    "/{auction_id}",
    response_model=BidRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter("bid", 60))],
)
def create_bid_for_auction(
    auction_id: int,
    payload: BidCreate,
    current_user: CurrentVerifiedUser,
    db: DbSession,
    request: Request,
) -> Bid:
    return BidService(db).place_bid(
        auction_id,
        current_user,
        payload,
        ip=client_ip(request),
        device_id=device_id(request),
        user_agent=_user_agent(request),
        idempotency_key=_idempotency_key(request),
    )


@router.post("/{bid_id}/retract", response_model=BidRead)
def retract_bid(
    bid_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> Bid:
    """Foydalanuvchi o'z bidini qaytarib oladi (typo/xato stavka)."""
    return BidService(db).retract_bid(bid_id, current_user)


@router.post("/{bid_id}/invalidate", response_model=BidRead)
def invalidate_bid(
    bid_id: int,
    payload: BidInvalidate,
    current_admin: CurrentAdminUser,
    db: DbSession,
) -> Bid:
    """Admin bidni bekor qiladi (shill/firibgarlik) — joriy narx qayta hisoblanadi."""
    return BidService(db).invalidate_bid(bid_id, current_admin, payload.reason)
