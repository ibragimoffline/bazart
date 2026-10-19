"""Second-chance offer testlari: reserve bajarilmaganda sotuvchiga taklif.

Oqim: eng yuqori bid reserve'dan past -> close -> RESERVE_NOT_MET + taklif.
Sotuvchi 24 soat ichida qabul qilsa -> ENDED + deal. Muddat o'tsa -> rad.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.deal import Deal
from app.models.enums import AuctionStatus, UserRole
from tests.conftest import create_auction, create_item, create_user


def _reserve_not_met_auction(client: TestClient, db_session: Session):
    seller = create_user(client, db_session, email="seller@example.com", role=UserRole.SELLER)
    bidder = create_user(client, db_session, email="bidder@example.com")
    item = create_item(client, seller, starting_price="5000000")
    auction = create_auction(
        client,
        seller,
        item["id"],
        minimum_bid_increment="100",
        reserve_price="20000000",
    )
    bid = client.post(
        f"/api/v1/bids/{auction['id']}",
        headers=bidder.headers,
        json={"amount": "6000000"},
    )
    assert bid.status_code == 201, bid.text

    close = client.post(f"/api/v1/auctions/{auction['id']}/close", headers=seller.headers)
    assert close.status_code == 200, close.text
    assert close.json()["status"] == "reserve_not_met"
    return seller, bidder, auction


def test_close_below_reserve_offers_second_chance(client: TestClient, db_session: Session) -> None:
    seller, bidder, auction = _reserve_not_met_auction(client, db_session)

    db_session.expire_all()
    row = db_session.get(Auction, auction["id"])
    assert row is not None
    assert row.status == AuctionStatus.RESERVE_NOT_MET
    assert row.second_chance_offered_at is not None
    assert row.second_chance_expires_at is not None


def test_reserve_price_never_exposed_in_read(client: TestClient, db_session: Session) -> None:
    seller, bidder, auction = _reserve_not_met_auction(client, db_session)
    body = client.get(f"/api/v1/auctions/{auction['id']}").json()
    # Reserve qiymati oshkor bo'lmaydi, faqat bor/yo'q va bajarilgan/yo'q.
    assert "reserve_price" not in body
    assert body["has_reserve"] is True
    assert body["reserve_met"] is False


def test_seller_accepts_second_chance_creates_order(
    client: TestClient, db_session: Session
) -> None:
    seller, bidder, auction = _reserve_not_met_auction(client, db_session)

    resp = client.post(
        f"/api/v1/auctions/{auction['id']}/second-chance/accept",
        headers=seller.headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ended"
    assert resp.json()["winner_id"] == bidder.id

    deal = db_session.execute(
        select(Deal).where(Deal.auction_id == auction["id"])
    ).scalar_one_or_none()
    assert deal is not None
    assert deal.buyer_id == bidder.id
    assert deal.final_price == 6_000_000


def test_expired_second_chance_rejected(client: TestClient, db_session: Session) -> None:
    seller, bidder, auction = _reserve_not_met_auction(client, db_session)

    db_session.expire_all()
    row = db_session.get(Auction, auction["id"])
    assert row is not None
    row.second_chance_expires_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.add(row)
    db_session.commit()

    resp = client.post(
        f"/api/v1/auctions/{auction['id']}/second-chance/accept",
        headers=seller.headers,
    )
    assert resp.status_code == 409


def test_non_seller_cannot_accept_second_chance(client: TestClient, db_session: Session) -> None:
    seller, bidder, auction = _reserve_not_met_auction(client, db_session)

    resp = client.post(
        f"/api/v1/auctions/{auction['id']}/second-chance/accept",
        headers=bidder.headers,
    )
    assert resp.status_code == 403
