from fastapi import APIRouter

from app.core.dependencies import CurrentActiveUser, CurrentAdminUser, DbSession
from app.models.deal import Deal
from app.schemas.deal import DealRead, DealStatusUpdate
from app.services.deal_service import DealService

router = APIRouter()


@router.get("/buyer", response_model=list[DealRead])
def read_buyer_deals(current_user: CurrentActiveUser, db: DbSession) -> list[Deal]:
    return DealService(db).list_buyer_deals(current_user)


@router.get("/seller", response_model=list[DealRead])
def read_seller_deals(current_user: CurrentActiveUser, db: DbSession) -> list[Deal]:
    return DealService(db).list_seller_deals(current_user)


@router.get("/admin", response_model=list[DealRead])
def read_admin_deals(current_user: CurrentAdminUser, db: DbSession) -> list[Deal]:
    return DealService(db).list_admin_deals(current_user)


@router.get("/{deal_id}", response_model=DealRead)
def read_deal(deal_id: int, current_user: CurrentActiveUser, db: DbSession) -> Deal:
    return DealService(db).get_deal_for_user(deal_id, current_user)


@router.patch("/{deal_id}/status", response_model=DealRead)
def update_deal_status(
    deal_id: int,
    payload: DealStatusUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
) -> Deal:
    return DealService(db).update_deal_status(deal_id, payload.status, current_user)
