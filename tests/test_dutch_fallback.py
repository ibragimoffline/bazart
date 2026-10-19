"""Gibrid model: taklifsiz tugagan auksion (sotuvchi roziligi bilan) 3 kunlik
pasayuvchi (golland) auksionga avtomatik o'tadi.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.enums import AuctionStatus, NotificationType, PricingMode
from app.models.notification import Notification
from app.models.watchlist import Watchlist
from app.money import calc_descending_price, calc_dutch_step
from app.services.auction_closer import close_due_auctions
from tests.conftest import AuthenticatedUser, create_bid, create_item, create_user

START = 100_000_000  # 1 000 000 so'm
FLOOR = 70_000_000  # 700 000 so'm


def _auction(client: TestClient, seller: AuthenticatedUser, **extra):
    item = create_item(client, seller, starting_price=str(START))
    now = datetime.now(UTC)
    return client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "100",
            **extra,
        },
    )


def _expire(db: Session, auction_id: int) -> None:
    db.expire_all()
    db.get(Auction, auction_id).end_time = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()


# --- Hisob ----------------------------------------------------------------------


def test_dutch_step_reaches_floor_in_time() -> None:
    step = calc_dutch_step(START, FLOOR, 60)
    assert step == 500_000  # 300 000 so'm / 60 = 5 000 so'm
    assert calc_descending_price(START, step, 60, FLOOR) == FLOOR
    # Yaxlitlash yuqoriga (1 so'mga): narx belgilangan vaqtdan kechikmaydi.
    odd = calc_dutch_step(1_000_000, 1, 7)
    assert odd % 100 == 0 and odd * 7 >= 1_000_000 - 1
    with pytest.raises(ValueError):
        calc_dutch_step(START, START, 60)


# --- Rozilik --------------------------------------------------------------------


def test_consent_validation(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    assert _auction(client, seller, dutch_fallback_floor=str(START)).status_code == 400
    descending = _auction(
        client,
        seller,
        pricing_mode="descending",
        price_decrement="1000",
        price_drop_interval_minutes=60,
        reserve_price=str(FLOOR),
        dutch_fallback_floor=str(FLOOR),
    )
    assert descending.status_code == 422
    ok = _auction(client, seller, dutch_fallback_floor=str(FLOOR))
    assert ok.status_code == 201
    body = ok.json()
    # Rozilik ommaga oshkor bo'lmaydi: xaridorlar arzonlashuvni kutib taklif bermay qolardi.
    assert "dutch_fallback_floor" not in body
    assert "dutch_fallback_enabled" not in body
    db_session.expire_all()
    assert db_session.get(Auction, body["id"]).dutch_fallback_floor == FLOOR


# --- O'tish ---------------------------------------------------------------------


def test_unsold_auction_continues_as_dutch(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    old = _auction(client, seller, dutch_fallback_floor=str(FLOOR)).json()
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": old["id"]})
    _expire(db_session, old["id"])

    assert close_due_auctions(db_session) == 1

    closed = client.get(f"/api/v1/auctions/{old['id']}").json()
    assert closed["status"] == "ended"
    assert closed["winner_id"] is None
    new_id = closed["continued_as_auction_id"]
    assert new_id is not None

    new = client.get(f"/api/v1/auctions/{new_id}").json()
    assert new["status"] == "active"
    assert new["pricing_mode"] == "descending"
    assert new["starting_price"] == str(START)
    assert new["current_price"] == str(START)
    assert new["price_decrement"] == "500000"
    assert new["price_drop_interval_minutes"] == 60
    assert new["duration_days"] == 3
    db_session.expire_all()
    assert db_session.get(Auction, new_id).dutch_fallback_floor is None  # zanjir yo'q
    span = datetime.fromisoformat(new["end_time"]) - datetime.fromisoformat(new["start_time"])
    assert span == timedelta(days=3)

    new_item = client.get(f"/api/v1/items/{new['item_id']}").json()
    assert new_item["relisted_from_id"] == old["item_id"]
    assert new_item["status"] == "active"

    db_session.expire_all()
    stored = db_session.get(Auction, new_id)
    assert stored.reserve_price == FLOOR  # pastki chegara = sotuvchi roziligi

    # Kuzatuvchi yangi auksionga ko'chdi va xabardor qilindi; sotuvchi ham.
    assert db_session.scalar(
        select(Watchlist).where(Watchlist.user_id == watcher.id, Watchlist.auction_id == new_id)
    )
    notified = {
        n.user_id
        for n in db_session.scalars(
            select(Notification).where(Notification.type == NotificationType.DUTCH_STARTED)
        )
    }
    assert notified == {seller.id, watcher.id}

    # Vaqt o'tsa narx tushadi (narx vaqtdan hisoblanadi).
    stored.start_time = datetime.now(UTC) - timedelta(minutes=125)
    db_session.commit()
    assert client.get(f"/api/v1/auctions/{new_id}").json()["current_price"] == str(
        START - 2 * 500_000
    )


def test_continuation_does_not_chain(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    old = _auction(client, seller, dutch_fallback_floor=str(FLOOR)).json()
    _expire(db_session, old["id"])
    close_due_auctions(db_session)
    new_id = client.get(f"/api/v1/auctions/{old['id']}").json()["continued_as_auction_id"]

    _expire(db_session, new_id)
    assert close_due_auctions(db_session) == 1
    ended = client.get(f"/api/v1/auctions/{new_id}").json()
    assert ended["status"] == "ended"
    assert ended["continued_as_auction_id"] is None
    assert len(db_session.scalars(select(Auction)).all()) == 2


def test_no_consent_keeps_old_behaviour(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    old = _auction(client, seller).json()
    _expire(db_session, old["id"])
    close_due_auctions(db_session)
    closed = client.get(f"/api/v1/auctions/{old['id']}").json()
    assert closed["status"] == "ended"
    assert closed["continued_as_auction_id"] is None
    assert len(db_session.scalars(select(Auction)).all()) == 1


def test_sold_or_reserve_not_met_does_not_continue(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="bidder@example.com")

    sold = _auction(client, seller, dutch_fallback_floor=str(FLOOR)).json()
    create_bid(client, bidder, sold["id"], amount=str(START + 100))
    _expire(db_session, sold["id"])

    unmet = _auction(
        client, seller, dutch_fallback_floor=str(FLOOR), reserve_price=str(START * 2)
    ).json()
    create_bid(client, bidder, unmet["id"], amount=str(START + 100))
    _expire(db_session, unmet["id"])

    assert close_due_auctions(db_session) == 2
    db_session.expire_all()
    assert db_session.get(Auction, sold["id"]).status == AuctionStatus.ENDED
    assert db_session.get(Auction, unmet["id"]).status == AuctionStatus.RESERVE_NOT_MET
    descending = db_session.scalars(
        select(Auction).where(Auction.pricing_mode == PricingMode.DESCENDING)
    ).all()
    assert descending == []


def test_manual_relist_blocked_after_continuation(client: TestClient, db_session: Session) -> None:
    """Davom etgan lotni sotuvchi qo'lda yana qayta joylay olmaydi — bitta tovar ikki marta emas."""
    seller = create_user(client, db_session, email="seller@example.com")
    old = _auction(client, seller, dutch_fallback_floor=str(FLOOR)).json()
    _expire(db_session, old["id"])
    close_due_auctions(db_session)
    relist = client.post(
        f"/api/v1/auctions/{old['id']}/relist",
        headers=seller.headers,
        json={"duration_days": 3, "starting_price": "90000000"},
    )
    assert relist.status_code == 409
