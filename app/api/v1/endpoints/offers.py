from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentActiveUser, CurrentUser, CurrentVerifiedUser, DbSession
from app.models.enums import OfferParty, OfferStatus
from app.models.offer import Offer
from app.schemas.offer import OfferCounter, OfferRead
from app.services.offer_service import OfferService

router = APIRouter()
RoleQuery = Annotated[OfferParty, Query()]
OfferStatusQuery = Annotated[OfferStatus | None, Query(alias="status")]


@router.get("", response_model=list[OfferRead])
def read_my_offers(
    current_user: CurrentUser,
    db: DbSession,
    role: RoleQuery = OfferParty.BUYER,
    status_filter: OfferStatusQuery = None,
) -> list[Offer]:
    """Mening takliflarim: role=buyer — yuborganlarim, role=seller — kelganlar."""
    return OfferService(db).list_mine(current_user, role, status_filter)


@router.get("/{offer_id}", response_model=OfferRead)
def read_offer(offer_id: int, current_user: CurrentUser, db: DbSession) -> Offer:
    return OfferService(db).get_for_user(offer_id, current_user)


@router.post("/{offer_id}/accept", response_model=OfferRead)
def accept_offer(offer_id: int, current_user: CurrentVerifiedUser, db: DbSession) -> Offer:
    """Navbatdagi tomon shartlarni qabul qiladi — zaxira kamayadi, deal yaratiladi."""
    return OfferService(db).accept(offer_id, current_user)


@router.post("/{offer_id}/counter", response_model=OfferRead)
def counter_offer(
    offer_id: int, payload: OfferCounter, current_user: CurrentVerifiedUser, db: DbSession
) -> Offer:
    return OfferService(db).counter(offer_id, current_user, payload)


@router.post("/{offer_id}/reject", response_model=OfferRead)
def reject_offer(offer_id: int, current_user: CurrentActiveUser, db: DbSession) -> Offer:
    return OfferService(db).reject(offer_id, current_user)


@router.post("/{offer_id}/withdraw", response_model=OfferRead)
def withdraw_offer(offer_id: int, current_user: CurrentActiveUser, db: DbSession) -> Offer:
    return OfferService(db).withdraw(offer_id, current_user)
