from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DbSession, current_admin_user, current_superadmin_user
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.deal import Deal
from app.models.enums import AuctionStatus, DealStatus, ItemStatus, UserRole
from app.models.item import Item
from app.models.user import User
from app.schemas.admin import AdminStatsRead, UserRoleUpdate
from app.schemas.auction import AuctionRead
from app.schemas.bid import BidRead
from app.schemas.deal import DealRead
from app.schemas.item import ItemRead
from app.schemas.user import UserRead
from app.services.admin_service import AdminService

router = APIRouter()

AdminUser = Annotated[User, Depends(current_admin_user)]
SuperAdminUser = Annotated[User, Depends(current_superadmin_user)]
SkipQuery = Annotated[int, Query(ge=0)]
LimitQuery = Annotated[int, Query(ge=1, le=100)]
SearchQuery = Annotated[str | None, Query(max_length=120)]


@router.get("/users", response_model=list[UserRead])
def admin_read_users(
    _admin: AdminUser,
    db: DbSession,
    search: SearchQuery = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
) -> list[User]:
    return AdminService(db).list_users(
        search=search,
        role=role,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.post("/users/{user_id}/block", response_model=UserRead)
def admin_block_user(user_id: int, admin: AdminUser, db: DbSession) -> User:
    return AdminService(db).block_user(user_id, admin)


@router.post("/users/{user_id}/unblock", response_model=UserRead)
def admin_unblock_user(user_id: int, admin: AdminUser, db: DbSession) -> User:
    return AdminService(db).unblock_user(user_id, admin)


@router.patch("/users/{user_id}/role", response_model=UserRead)
def admin_change_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    superadmin: SuperAdminUser,
    db: DbSession,
) -> User:
    # Rol berish — faqat superadmin. Aks holda admin o'zini/boshqani ko'tarib
    # huquqni cheksiz tarqatishi mumkin edi.
    return AdminService(db).change_user_role(user_id, payload.role, superadmin)


@router.get("/items", response_model=list[ItemRead])
def admin_read_items(
    _admin: AdminUser,
    db: DbSession,
    search: SearchQuery = None,
    status_filter: Annotated[ItemStatus | None, Query(alias="status")] = None,
    seller_id: int | None = None,
    category_id: int | None = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
) -> list[Item]:
    return AdminService(db).list_items(
        search=search,
        status_filter=status_filter,
        seller_id=seller_id,
        category_id=category_id,
        skip=skip,
        limit=limit,
    )


@router.post("/items/{item_id}/approve", response_model=ItemRead)
def admin_approve_item(item_id: int, _admin: AdminUser, db: DbSession) -> Item:
    return AdminService(db).approve_item(item_id)


@router.post("/items/{item_id}/reject", response_model=ItemRead)
def admin_reject_item(item_id: int, _admin: AdminUser, db: DbSession) -> Item:
    return AdminService(db).reject_item(item_id)


@router.get("/auctions", response_model=list[AuctionRead])
def admin_read_auctions(
    _admin: AdminUser,
    db: DbSession,
    status_filter: Annotated[AuctionStatus | None, Query(alias="status")] = None,
    seller_id: int | None = None,
    item_id: int | None = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
) -> list[Auction]:
    return AdminService(db).list_auctions(
        status_filter=status_filter,
        seller_id=seller_id,
        item_id=item_id,
        skip=skip,
        limit=limit,
    )


@router.post("/auctions/{auction_id}/cancel", response_model=AuctionRead)
def admin_cancel_auction(auction_id: int, _admin: AdminUser, db: DbSession) -> Auction:
    return AdminService(db).cancel_auction(auction_id)


@router.get("/bids", response_model=list[BidRead])
def admin_read_bids(
    _admin: AdminUser,
    db: DbSession,
    auction_id: int | None = None,
    bidder_id: int | None = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
) -> list[Bid]:
    return AdminService(db).list_bids(
        auction_id=auction_id,
        bidder_id=bidder_id,
        skip=skip,
        limit=limit,
    )


@router.get("/deals", response_model=list[DealRead])
def admin_read_deals(
    _admin: AdminUser,
    db: DbSession,
    status_filter: Annotated[DealStatus | None, Query(alias="status")] = None,
    buyer_id: int | None = None,
    seller_id: int | None = None,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
) -> list[Deal]:
    return AdminService(db).list_deals(
        status_filter=status_filter,
        buyer_id=buyer_id,
        seller_id=seller_id,
        skip=skip,
        limit=limit,
    )


@router.get("/statistics", response_model=AdminStatsRead)
def admin_read_statistics(_admin: AdminUser, db: DbSession) -> dict:
    return AdminService(db).get_statistics()


# Backward-compatible aliases for the earlier skeleton route names.
@router.get("/listings", response_model=list[ItemRead])
def admin_read_listings_alias(
    _admin: AdminUser,
    db: DbSession,
    skip: SkipQuery = 0,
    limit: LimitQuery = 100,
) -> list[Item]:
    return AdminService(db).list_items(skip=skip, limit=limit)
