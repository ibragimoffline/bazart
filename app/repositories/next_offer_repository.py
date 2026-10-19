from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.next_bidder_offer import NextBidderOffer


class NextOfferRepository:
    """Keyingi bidderga takliflar (E2.10). Yozuvlar o'chirilmaydi — kim taklif olgani tarixi."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, offer: NextBidderOffer) -> NextBidderOffer:
        self.db.add(offer)
        self.db.flush()
        return offer

    def list_for_auction(self, auction_id: int) -> list[NextBidderOffer]:
        statement = (
            select(NextBidderOffer)
            .where(NextBidderOffer.auction_id == auction_id)
            .order_by(NextBidderOffer.offered_at.desc())
        )
        return list(self.db.scalars(statement))

    def get_for_bidder(self, auction_id: int, bidder_id: int) -> NextBidderOffer | None:
        statement = select(NextBidderOffer).where(
            NextBidderOffer.auction_id == auction_id, NextBidderOffer.bidder_id == bidder_id
        )
        return self.db.scalar(statement)
