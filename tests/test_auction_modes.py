"""Auksion rejimlari: rejalashtirilgan auksionni o'z vaqtida faollashtirish, narx rejimini
boshlanishgacha o'zgartirish va pasayuvchi auksion narx prognozi (xaridor uchun).
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.enums import AuctionStatus, PricingMode
from app.services.auction_closer import close_due_auctions
from tests.conftest import AuthenticatedUser, create_item, create_user

START = 10_000


def _create(
    client: TestClient,
    seller: AuthenticatedUser,
    *,
    start_in: timedelta = timedelta(minutes=10),
    days: int = 3,
    **extra,
) -> dict:
    item = create_item(client, seller, starting_price=str(START))
    start = datetime.now(UTC) + start_in
    resp = client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(days=days)).isoformat(),
            "minimum_bid_increment": "100",
            **extra,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _shift(db: Session, auction_id: int, **fields) -> None:
    db.expire_all()
    auction = db.get(Auction, auction_id)
    for key, value in fields.items():
        setattr(auction, key, value)
    db.commit()


DESCENDING = {
    "pricing_mode": "descending",
    "price_decrement": "100",
    "price_drop_interval_minutes": 60,
    "reserve_price": "6000",
}


# --- O'z vaqtida faollashtirish -------------------------------------------------


def test_scheduled_auction_activates_on_time(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    auction = _create(client, seller)
    assert auction["status"] == "scheduled"

    assert close_due_auctions(db_session) == 0
    db_session.expire_all()
    assert db_session.get(Auction, auction["id"]).status == AuctionStatus.SCHEDULED

    _shift(db_session, auction["id"], start_time=datetime.now(UTC) - timedelta(minutes=1))
    close_due_auctions(db_session)
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "active"
    assert client.get(f"/api/v1/items/{auction['item_id']}").json()["status"] == "active"


def test_scheduled_auction_past_its_end_is_activated_then_closed(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    auction = _create(client, seller)
    now = datetime.now(UTC)
    _shift(
        db_session,
        auction["id"],
        start_time=now - timedelta(days=2),
        end_time=now - timedelta(minutes=1),
    )
    assert close_due_auctions(db_session) == 1
    assert client.get(f"/api/v1/auctions/{auction['id']}").json()["status"] == "ended"


def test_buy_now_activates_started_scheduled_auction(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    auction = _create(client, seller, **DESCENDING)
    resp = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert resp.status_code == 409  # hali boshlanmagan

    _shift(db_session, auction["id"], start_time=datetime.now(UTC) - timedelta(minutes=5))
    resp = client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ended"
    assert resp.json()["current_price"] == str(START)


# --- Narx rejimini boshlanishgacha o'zgartirish ---------------------------------


def test_seller_switches_mode_before_start(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    auction = _create(client, seller, buy_now_price="15000")
    url = f"/api/v1/auctions/{auction['id']}/pricing"

    to_dutch = client.patch(url, headers=seller.headers, json=DESCENDING)
    assert to_dutch.status_code == 200, to_dutch.text
    body = to_dutch.json()
    assert body["pricing_mode"] == "descending"
    assert body["buy_now_price"] is None  # eski rejim qoldig'i tozalandi
    assert body["price_decrement"] == "100"

    back = client.patch(
        url,
        headers=seller.headers,
        json={"pricing_mode": "ascending", "buy_now_price": "14000", "reserve_price": "12000"},
    )
    assert back.status_code == 200, back.text
    db_session.expire_all()
    stored = db_session.get(Auction, auction["id"])
    assert stored.pricing_mode == PricingMode.ASCENDING
    assert stored.price_decrement is None and stored.price_drop_interval_minutes is None
    assert stored.buy_now_price == 14_000 and stored.reserve_price == 12_000


def test_pricing_update_rules(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    other = create_user(client, db_session, email="other@example.com")
    auction = _create(client, seller)
    url = f"/api/v1/auctions/{auction['id']}/pricing"

    assert client.patch(url, headers=other.headers, json=DESCENDING).status_code == 403
    no_floor = {**DESCENDING, "reserve_price": None}
    assert client.patch(url, headers=seller.headers, json=no_floor).status_code == 400
    high_floor = {**DESCENDING, "reserve_price": str(START)}
    assert client.patch(url, headers=seller.headers, json=high_floor).status_code == 400
    with_buy_now = {**DESCENDING, "buy_now_price": "20000"}
    assert client.patch(url, headers=seller.headers, json=with_buy_now).status_code == 422

    # Boshlangach qoidalar o'zgarmaydi.
    _shift(db_session, auction["id"], start_time=datetime.now(UTC) - timedelta(minutes=1))
    assert client.patch(url, headers=seller.headers, json=DESCENDING).status_code == 409


# --- Narx prognozi (xaridor uchun) ----------------------------------------------


def test_price_forecast_lists_daily_drops_until_floor(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    auction = _create(client, seller, start_in=timedelta(minutes=-1), **DESCENDING)
    forecast = client.get(f"/api/v1/auctions/{auction['id']}").json()["price_forecast"]
    # Kuniga 24 x 100 = 2 400 pasayadi: 1-kun 7 600, 2-kun chegara 6 000 (to'xtaydi).
    assert [(p["days_from_now"], p["price"], p["is_end"]) for p in forecast] == [
        (1, "7600", False),
        (2, "6000", False),
    ]


def test_price_forecast_ends_at_auction_end(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    slow = {**DESCENDING, "price_decrement": "10", "reserve_price": "100"}
    auction = _create(client, seller, start_in=timedelta(minutes=-1), days=3, **slow)
    forecast = client.get(f"/api/v1/auctions/{auction['id']}").json()["price_forecast"]
    # Tugash = boshlanish + 3 kun -> 72 oraliq x 10 = 720 -> 9 280.
    assert [p["price"] for p in forecast] == ["9760", "9520", "9280"]
    assert forecast[-1]["is_end"] is True


def test_no_forecast_for_ascending_or_sold(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    ascending = _create(client, seller, start_in=timedelta(minutes=-1))
    assert client.get(f"/api/v1/auctions/{ascending['id']}").json()["price_forecast"] == []

    dutch = _create(client, seller, start_in=timedelta(minutes=-1), **DESCENDING)
    client.post(f"/api/v1/auctions/{dutch['id']}/buy-now", headers=buyer.headers)
    assert client.get(f"/api/v1/auctions/{dutch['id']}").json()["price_forecast"] == []
