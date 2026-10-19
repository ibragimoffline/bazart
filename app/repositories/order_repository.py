from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.enums import OrderStatus
from app.models.offer import Offer
from app.models.order import Order
from app.money import calc_line_total


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, order_id: int) -> Order | None:
        return self.db.get(Order, order_id)

    def get_by_auction_id(self, auction_id: int) -> Order | None:
        statement = select(Order).where(Order.auction_id == auction_id)
        return self.db.scalar(statement)

    def create_for_auction(self, auction: Auction) -> Order:
        if auction.winner_id is None or auction.winning_bid is None:
            raise ValueError("Cannot create order without a winning bidder and winning bid")

        order = Order(
            auction_id=auction.id,
            item_id=auction.item_id,
            buyer_id=auction.winner_id,
            seller_id=auction.seller_id,
            quantity=1,
            unit_price=auction.winning_bid.amount,
            final_price=auction.winning_bid.amount,
        )
        self.db.add(order)
        self.db.flush()
        return order

    def create_for_offer(self, offer: Offer) -> Order:
        """Qabul qilingan taklifdan order. COMMIT QILMAYDI (chaqiruvchi tranzaksiyasi)."""
        order = Order(
            offer_id=offer.id,
            item_id=offer.item_id,
            buyer_id=offer.buyer_id,
            seller_id=offer.seller_id,
            quantity=offer.quantity,
            unit_price=offer.unit_price,
            final_price=calc_line_total(offer.unit_price, offer.quantity),
        )
        self.db.add(order)
        self.db.flush()
        return order

    def list_for_buyer(self, buyer_id: int) -> list[Order]:
        statement = (
            select(Order).where(Order.buyer_id == buyer_id).order_by(Order.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_for_seller(self, seller_id: int) -> list[Order]:
        statement = (
            select(Order).where(Order.seller_id == seller_id).order_by(Order.created_at.desc())
        )
        return list(self.db.scalars(statement))

    def list_all(self) -> list[Order]:
        statement = select(Order).order_by(Order.created_at.desc())
        return list(self.db.scalars(statement))

    def update_status(self, order: Order, status: OrderStatus) -> Order:
        order.status = status
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order
