"""Closer worker'ning toza funksiyasi (`close_due_auctions`) uchun testlar.

Fon loop'ining o'zi test qilinmaydi (u faqat yoqilgan/non-test muhitda
ishlaydi) — biz to'g'ridan-to'g'ri testlanadigan `close_due_auctions`
funksiyasini sinaymiz: muddati o'tgan ACTIVE auksion yopiladi,
kelajakdagisi tegilmaydi.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.deal import Deal
from app.models.enums import AuctionStatus, UserRole
from app.services.auction_closer import close_due_auctions
from tests.conftest import create_auction, create_bid, create_item, create_user


def _expire_end_time(db_session: Session, auction_id: int) -> None:
    """Auksion `end_time` ni o'tmishga suradi.

    Bid qo'yish uchun auksion faol va `end_time` kelajakda bo'lishi kerak
    edi; muddati o'tganini simulyatsiya qilish uchun endi uni o'tmishga
    ko'chiramiz (state machine emas — bu shunchaki vaqtni oldinga surish).
    """
    db_session.expire_all()
    auction = db_session.get(Auction, auction_id)
    assert auction is not None
    auction.end_time = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(auction)
    db_session.commit()


def test_close_due_auction_with_bid_creates_order(client: TestClient, db_session: Session) -> None:
    """Muddati o'tgan bidli faol auksion → ENDED + deal, qaytgan son 1."""
    seller = create_user(client, db_session, email="seller@example.com", role=UserRole.SELLER)
    bidder = create_user(client, db_session, email="bidder@example.com")

    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"], end_delta=timedelta(days=1))
    create_bid(client, bidder, auction["id"], amount="1100")

    # Endi muddatini o'tmishga surib, closer'ni chaqiramiz.
    _expire_end_time(db_session, auction["id"])

    closed = close_due_auctions(db_session)

    assert closed == 1

    db_session.expire_all()
    closed_auction = db_session.get(Auction, auction["id"])
    assert closed_auction is not None
    assert closed_auction.status == AuctionStatus.ENDED
    assert closed_auction.winner_id == bidder.id

    deal = db_session.execute(
        select(Deal).where(Deal.auction_id == auction["id"])
    ).scalar_one_or_none()
    assert deal is not None
    assert deal.buyer_id == bidder.id


def test_close_does_not_touch_future_auction(client: TestClient, db_session: Session) -> None:
    """`end_time` kelajakda bo'lgan faol auksion yopilmaydi, qaytgan son 0."""
    seller = create_user(client, db_session, email="seller@example.com", role=UserRole.SELLER)

    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"], end_delta=timedelta(days=1))

    closed = close_due_auctions(db_session)

    assert closed == 0

    db_session.expire_all()
    open_auction = db_session.get(Auction, auction["id"])
    assert open_auction is not None
    assert open_auction.status == AuctionStatus.ACTIVE
