from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.enums import OrderStatus, is_admin
from app.models.order import Order
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.services.offer_service import OfferService
from app.services.order_state import InvalidOrderTransition, assert_order_transition


class OrderService:
    """Order/transaction creation skeleton for completed auctions."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)

    def create_order_for_winning_auction(self, auction: Auction) -> Order | None:
        # TODO: Attach payment intent, pickup instructions, taxes, and platform fees.
        if auction.winner_id is None or auction.winning_bid is None:
            return None

        existing_order = self.orders.get_by_auction_id(auction.id)
        if existing_order is not None:
            return existing_order

        return self.orders.create_for_auction(auction)

    def get_order_for_user(self, order_id: int, user: User) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if is_admin(user.role) or user.id in {order.buyer_id, order.seller_id}:
            return order
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")

    def list_buyer_orders(self, buyer: User) -> list[Order]:
        return self.orders.list_for_buyer(buyer.id)

    def list_seller_orders(self, seller: User) -> list[Order]:
        return self.orders.list_for_seller(seller.id)

    def list_admin_orders(self, admin: User) -> list[Order]:
        if not is_admin(admin.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )
        return self.orders.list_all()

    def update_order_status(self, order_id: int, new_status: OrderStatus, actor: User) -> Order:
        order = self.orders.get(order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if not is_admin(actor.role) and actor.id != order.seller_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin or seller can manage order status",
            )
        # Qo'lda status yozish faqat ruxsat etilgan o'tishlar orqali (grifing/
        # izchillik buzilishining oldi).
        try:
            assert_order_transition(order.status, new_status)
        except InvalidOrderTransition as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        if new_status == OrderStatus.CANCELLED:
            # Taklif bitimi bekor — donalar zaxiraga qaytadi (update_status commit qiladi).
            OfferService(self.db).restore_stock(order)
        return self.orders.update_status(order, new_status)
