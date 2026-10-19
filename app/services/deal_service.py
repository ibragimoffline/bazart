from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.deal import Deal
from app.models.enums import DealStatus, is_admin
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.services.deal_state import InvalidDealTransition, assert_deal_transition
from app.services.offer_service import OfferService


class DealService:
    """Deal/transaction creation skeleton for completed auctions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.deals = DealRepository(db)

    def create_deal_for_winning_auction(self, auction: Auction) -> Deal | None:
        if auction.winner_id is None or auction.winning_bid is None:
            return None

        existing_order = self.deals.get_by_auction_id(auction.id)
        if existing_order is not None:
            return existing_order

        return self.deals.create_for_auction(auction)

    def get_deal_for_user(self, deal_id: int, user: User) -> Deal:
        deal = self.deals.get(deal_id)
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        if is_admin(user.role) or user.id in {deal.buyer_id, deal.seller_id}:
            return deal
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your deal")

    def list_buyer_deals(self, buyer: User) -> list[Deal]:
        return self.deals.list_for_buyer(buyer.id)

    def list_seller_deals(self, seller: User) -> list[Deal]:
        return self.deals.list_for_seller(seller.id)

    def list_admin_deals(self, admin: User) -> list[Deal]:
        if not is_admin(admin.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )
        return self.deals.list_all()

    def update_deal_status(self, deal_id: int, new_status: DealStatus, actor: User) -> Deal:
        deal = self.deals.get(deal_id)
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")
        if not is_admin(actor.role) and actor.id != deal.seller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin or seller can manage deal status",
            )
        # Qo'lda status yozish faqat ruxsat etilgan o'tishlar orqali (grifing/
        # izchillik buzilishining oldi).
        try:
            assert_deal_transition(deal.status, new_status)
        except InvalidDealTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if new_status == DealStatus.CANCELLED:
            # Taklif bitimi bekor — donalar zaxiraga qaytadi (update_status commit qiladi).
            OfferService(self.db).restore_stock(deal)
        return self.deals.update_status(deal, new_status)
