from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.deal import Deal
from app.models.offer import Offer
from app.money import calc_line_total


class DealRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, deal_id: int) -> Deal | None:
        return self.db.get(Deal, deal_id)

    def get_by_auction_id(self, auction_id: int) -> Deal | None:
        statement = select(Deal).where(Deal.auction_id == auction_id)
        return self.db.scalar(statement)

    def create_for_auction(self, auction: Auction) -> Deal:
        if auction.winner_id is None or auction.winning_bid is None:
            raise ValueError("Cannot create deal without a winning bidder and winning bid")

        deal = Deal(
            auction_id=auction.id,
            item_id=auction.item_id,
            buyer_id=auction.winner_id,
            seller_id=auction.seller_id,
            quantity=1,
            unit_price=auction.winning_bid.amount,
            final_price=auction.winning_bid.amount,
            contacts_revealed_at=datetime.now(UTC),
        )
        self.db.add(deal)
        self.db.flush()
        return deal

    def create_for_offer(self, offer: Offer) -> Deal:
        """Qabul qilingan taklifdan deal. COMMIT QILMAYDI (chaqiruvchi tranzaksiyasi)."""
        deal = Deal(
            offer_id=offer.id,
            item_id=offer.item_id,
            buyer_id=offer.buyer_id,
            seller_id=offer.seller_id,
            quantity=offer.quantity,
            unit_price=offer.unit_price,
            final_price=calc_line_total(offer.unit_price, offer.quantity),
            contacts_revealed_at=datetime.now(UTC),
        )
        self.db.add(deal)
        self.db.flush()
        return deal

    def list_for_buyer(self, buyer_id: int) -> list[Deal]:
        statement = select(Deal).where(Deal.buyer_id == buyer_id).order_by(Deal.created_at.desc())
        return list(self.db.scalars(statement))

    def list_for_seller(self, seller_id: int) -> list[Deal]:
        statement = select(Deal).where(Deal.seller_id == seller_id).order_by(Deal.created_at.desc())
        return list(self.db.scalars(statement))

    def list_all(self) -> list[Deal]:
        statement = select(Deal).order_by(Deal.created_at.desc())
        return list(self.db.scalars(statement))

    def get_for_update(self, deal_id: int) -> Deal | None:
        """Kelishuv qatorini FOR UPDATE bilan oladi: "Sotildi" va "Tasdiqlayman" bir vaqtda
        kelsa, ikkalasi bir-birining yozuvini ko'rmay qolib kelishuv `agreed` da qotmasin."""
        return self.db.scalar(select(Deal).where(Deal.id == deal_id).with_for_update())
