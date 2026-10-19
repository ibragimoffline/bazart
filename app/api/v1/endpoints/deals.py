from fastapi import APIRouter

from app.core.dependencies import CurrentActiveUser, CurrentAdminUser, DbSession
from app.models.deal import Deal
from app.schemas.deal import DealCancel, DealDetail, DealRead, NextBidderOffer
from app.services.auction_service import AuctionService
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


@router.get("/{deal_id}", response_model=DealDetail)
def read_deal(deal_id: int, current_user: CurrentActiveUser, db: DbSession) -> DealDetail:
    """Kelishuv; ishtirokchiga ikkinchi tomon kontakti bilan. Begona — 404."""
    return DealService(db).detail_for_user(deal_id, current_user)


@router.post("/{deal_id}/complete", response_model=DealRead)
def complete_deal(deal_id: int, current_user: CurrentActiveUser, db: DbSession) -> Deal:
    """Sotuvchi: "Sotildi"."""
    return DealService(db).complete(deal_id, current_user)


@router.post("/{deal_id}/confirm", response_model=DealRead)
def confirm_deal(deal_id: int, current_user: CurrentActiveUser, db: DbSession) -> Deal:
    """Xaridor: "Tasdiqlayman"."""
    return DealService(db).confirm(deal_id, current_user)


@router.post("/{deal_id}/cancel", response_model=DealRead)
def cancel_deal(
    deal_id: int, payload: DealCancel, current_user: CurrentActiveUser, db: DbSession
) -> Deal:
    """Istalgan tomon (yoki admin), sabab bilan."""
    return DealService(db).cancel(deal_id, current_user, payload.reason)


@router.post("/{deal_id}/offer-next-bidder", response_model=NextBidderOffer)
def offer_next_bidder(
    deal_id: int, current_user: CurrentActiveUser, db: DbSession
) -> NextBidderOffer:
    """Sotuvchi: g'olib javob bermay bekor qilingan kelishuvdan keyin keyingi bidderga taklif."""
    offer = AuctionService(db).offer_next_bidder(deal_id, current_user)
    return NextBidderOffer.model_validate(offer)
