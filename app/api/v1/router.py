from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auctions,
    auth,
    bids,
    categories,
    complaints,
    deals,
    fraud,
    items,
    legal,
    messages,
    notifications,
    offers,
    regions,
    reviews,
    users,
    watchlist,
    ws,
)
from app.core.config import settings
from app.schemas.features import FeatureFlags

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(auctions.router, prefix="/auctions", tags=["auctions"])
api_router.include_router(bids.router, prefix="/bids", tags=["bids"])
api_router.include_router(deals.router, prefix="/deals", tags=["deals"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(fraud.router, prefix="/fraud", tags=["fraud"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(regions.router, prefix="/regions", tags=["regions"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(complaints.router, prefix="/complaints", tags=["complaints"])
api_router.include_router(legal.router, prefix="/legal", tags=["legal"])
api_router.include_router(offers.router, prefix="/offers", tags=["offers"])
api_router.include_router(ws.router, tags=["ws"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


@api_router.get("/features", response_model=FeatureFlags, tags=["health"])
def feature_flags() -> FeatureFlags:
    """Ochiq: UI qaysi sotish usullarini ko'rsatishini biladi (API ham shu bayroqni tekshiradi)."""
    return FeatureFlags(ascending_auction=settings.feature_ascending_auction)


@api_router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
