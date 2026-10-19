"""Pasayuvchi (golland) auksion: narx vaqtdan hisoblanadi, birinchi xarid yutadi.

Narx bazada saqlanmaydi — testlarda vaqt o'tishi `start_time` ni orqaga surish bilan
simulyatsiya qilinadi. Pul (narx) va poyga (ikki xaridor) shu yerda sinaladi.
"""

import threading
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.auction import Auction
from app.models.enums import AuctionStatus, NotificationType, PricingMode
from app.models.notification import Notification
from app.models.order import Order
from app.models.user import User
from app.money import calc_descending_price
from app.services.auction_closer import close_due_auctions
from app.services.auction_service import AuctionService
from app.services.ending_soon import notify_ending_soon
from app.services.price_schedule import elapsed_intervals, next_price_drop_at
from tests.conftest import AuthenticatedUser, create_item, create_user

START = 10_000  # tiyin
STEP = 1_000
FLOOR = 6_000
INTERVAL = 60  # daqiqa


def _descending(
    client: TestClient,
    seller: AuthenticatedUser,
    item_id: int,
    *,
    end_delta: timedelta = timedelta(days=3),
    **overrides,
):
    now = datetime.now(UTC)
    payload = {
        "item_id": item_id,
        "start_time": (now - timedelta(minutes=1)).isoformat(),
        "end_time": (now + end_delta).isoformat(),
        "pricing_mode": "descending",
        "price_decrement": str(STEP),
        "price_drop_interval_minutes": INTERVAL,
        "reserve_price": str(FLOOR),
        **overrides,
    }
    return client.post("/api/v1/auctions", headers=seller.headers, json=payload)


def _age(db: Session, auction_id: int, minutes: int) -> None:
    """Auksionni `minutes` daqiqa oldin boshlangandek qiladi (vaqt o'tishi)."""
    db.expire_all()
    auction = db.get(Auction, auction_id)
    auction.start_time = datetime.now(UTC) - timedelta(minutes=minutes)
    db.commit()


def _setup(client: TestClient, db: Session) -> tuple[AuthenticatedUser, AuthenticatedUser, dict]:
    seller = create_user(client, db, email="seller@example.com")
    buyer = create_user(client, db, email="buyer@example.com")
    item = create_item(client, seller, starting_price=str(START))
    auction = _descending(client, seller, item["id"])
    assert auction.status_code == 201, auction.text
    return seller, buyer, auction.json()


# --- Sof hisob (app/money + price_schedule) ------------------------------------


def test_calc_descending_price() -> None:
    assert calc_descending_price(START, STEP, 0, FLOOR) == START
    assert calc_descending_price(START, STEP, 3, FLOOR) == 7_000
    assert calc_descending_price(START, STEP, 4, FLOOR) == FLOOR
    assert calc_descending_price(START, STEP, 400, FLOOR) == FLOOR  # chegaradan past emas
    assert calc_descending_price(START, STEP, -2, FLOOR) == START
    with pytest.raises(ValueError):
        calc_descending_price(START, 0, 1, FLOOR)
    with pytest.raises(ValueError):
        calc_descending_price(START, STEP, 1, START + 1)


def test_schedule_intervals_and_next_drop() -> None:
    start = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)
    assert elapsed_intervals(start, start - timedelta(hours=1), INTERVAL) == 0
    assert elapsed_intervals(start, start + timedelta(minutes=59), INTERVAL) == 0
    assert elapsed_intervals(start, start + timedelta(minutes=125), INTERVAL) == 2
    common = dict(
        starting_price=START, price_decrement=STEP, interval_minutes=INTERVAL, floor_price=FLOOR
    )
    at = start + timedelta(minutes=125)
    assert next_price_drop_at(**common, start_time=start, at=at) == start + timedelta(hours=3)
    # Chegaraga yetgach keyingi pasayish yo'q.
    assert next_price_drop_at(**common, start_time=start, at=start + timedelta(hours=9)) is None


# --- Yaratish qoidalari ---------------------------------------------------------


def test_descending_creation_rules(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")

    def item_id() -> int:
        return create_item(client, seller, starting_price=str(START))["id"]

    assert _descending(client, seller, item_id(), price_decrement=None).status_code == 422
    assert _descending(client, seller, item_id(), buy_now_price="9000").status_code == 422
    assert _descending(client, seller, item_id(), reserve_price=None).status_code == 400
    assert _descending(client, seller, item_id(), reserve_price=str(START)).status_code == 400
    assert _descending(client, seller, item_id(), price_drop_interval_minutes=1).status_code == 422
    # O'suvchi auksionda qadam maydoni ishlatilmaydi.
    now = datetime.now(UTC)
    ascending = client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item_id(),
            "start_time": now.isoformat(),
            "duration_days": 3,
            "price_decrement": str(STEP),
        },
    )
    assert ascending.status_code == 422


# --- Jonli narx -----------------------------------------------------------------


def test_price_is_computed_from_time_not_stored(client: TestClient, db_session: Session) -> None:
    _, _, auction = _setup(client, db_session)
    assert auction["pricing_mode"] == "descending"
    assert auction["current_price"] == str(START)
    assert auction["has_reserve"] is False  # chegara — "qoplanadigan" rezerv emas
    assert auction["reserve_met"] is None
    assert "reserve_price" not in auction
    assert auction["buy_now_available"] is True

    _age(db_session, auction["id"], minutes=125)  # 2 oraliq o'tdi
    live = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert live["current_price"] == "8000"
    drop = datetime.fromisoformat(live["next_price_drop_at"])
    assert timedelta(minutes=50) < drop - datetime.now(UTC) <= timedelta(minutes=56)

    db_session.expire_all()
    assert db_session.get(Auction, auction["id"]).current_price == START  # bazada tegilmagan

    _age(db_session, auction["id"], minutes=60 * 20)
    floor = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert floor["current_price"] == str(FLOOR)
    assert floor["next_price_drop_at"] is None


def test_bids_are_rejected(client: TestClient, db_session: Session) -> None:
    _, buyer, auction = _setup(client, db_session)
    resp = client.post(
        f"/api/v1/auctions/{auction['id']}/bids", headers=buyer.headers, json={"amount": "11000"}
    )
    assert resp.status_code == 409


# --- Xarid ----------------------------------------------------------------------


def test_buy_now_pays_live_price_and_freezes_it(client: TestClient, db_session: Session) -> None:
    seller, buyer, auction = _setup(client, db_session)
    assert (
        client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=seller.headers).status_code
        == 400
    )
    _age(db_session, auction["id"], minutes=185)  # 3 oraliq -> 7000

    resp = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ended"
    assert body["winner_id"] == buyer.id
    assert body["current_price"] == "7000"
    assert body["buy_now_available"] is False
    assert body["next_price_drop_at"] is None

    order = db_session.scalar(select(Order).where(Order.auction_id == auction["id"]))
    assert order is not None and order.final_price == 7_000 and order.buyer_id == buyer.id

    # Vaqt o'tsa ham sotuv narxi o'zgarmaydi.
    _age(db_session, auction["id"], minutes=60 * 20)
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["current_price"] == "7000"

    other = create_user(client, db_session, email="late@example.com")
    late = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=other.headers)
    assert late.status_code == 409


def test_unsold_descending_auction_closes_without_order(
    client: TestClient, db_session: Session
) -> None:
    _, buyer, auction = _setup(client, db_session)
    db_session.expire_all()
    stored = db_session.get(Auction, auction["id"])
    stored.start_time = datetime.now(UTC) - timedelta(hours=10)
    stored.end_time = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    # Muddat o'tgan, closer hali yopmagan — xarid yo'q.
    resp = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert resp.status_code == 409

    assert close_due_auctions(db_session) == 1
    closed = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert closed["status"] == "ended"
    assert closed["winner_id"] is None
    assert closed["current_price"] == str(FLOOR)  # tugash paytidagi narx
    assert db_session.scalar(select(Order).where(Order.auction_id == auction["id"])) is None


def test_ending_soon_quotes_live_price(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    item = create_item(client, seller, starting_price=str(START))
    auction = _descending(client, seller, item["id"], end_delta=timedelta(minutes=30)).json()
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": auction["id"]})
    _age(db_session, auction["id"], minutes=125)

    assert notify_ending_soon(db_session) == 1
    note = db_session.scalar(
        select(Notification).where(Notification.type == NotificationType.ENDING_SOON)
    )
    assert note is not None
    assert note.payload["current_price"] == "8000"


# --- Haqiqiy parallel xarid (alohida ulanishlar) ---------------------------------


def test_parallel_buy_now_only_one_wins(
    client: TestClient, db_session: Session, db_engine: Engine
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyers = [create_user(client, db_session, email=f"b{i}@example.com") for i in range(8)]
    item = create_item(client, seller, starting_price=str(START))
    auction_id = _descending(client, seller, item["id"]).json()["id"]

    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    barrier = threading.Barrier(len(buyers))
    results: list[str] = []
    lock = threading.Lock()

    def buy(user_id: int) -> None:
        session = SessionMaker()
        try:
            actor = session.get(User, user_id)
            barrier.wait()
            try:
                AuctionService(session).buy_now(auction_id, actor)
                outcome = "ok"
            except Exception as exc:  # noqa: BLE001
                outcome = type(exc).__name__
            with lock:
                results.append(outcome)
        finally:
            session.close()

    threads = [threading.Thread(target=buy, args=(b.id,)) for b in buyers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count("ok") == 1, results
    check = SessionMaker()
    try:
        stored = check.get(Auction, auction_id)
        assert stored.status == AuctionStatus.ENDED
        assert stored.pricing_mode == PricingMode.DESCENDING
        orders = check.scalars(select(Order).where(Order.auction_id == auction_id)).all()
        assert len(orders) == 1
        assert orders[0].buyer_id == stored.winner_id
    finally:
        check.close()
