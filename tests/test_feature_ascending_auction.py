"""FEATURE_ASCENDING_AUCTION bayrog'i: o'suvchi auksion vaqtincha o'chiriladi.

O'chirilganda YANGI o'suvchi auksion yaratilmaydi (yaratish, rejimni almashtirish, qayta
joylash — 409). Mavjud o'suvchi auksionlar o'z qoidasida tugaydi: bid, yopish, g'olib,
Dutch-fallback. Pasayuvchi auksion va taklifli savdo o'zgarmaydi. Yoqilganda — avvalgidek.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auction import Auction
from app.models.enums import AuctionStatus, PricingMode
from app.services.auction_closer import close_due_auctions
from app.services.auction_service import ASCENDING_DISABLED
from tests.conftest import AuthenticatedUser, create_bid, create_item, create_user

START = 10_000
DESCENDING = {
    "pricing_mode": "descending",
    "price_decrement": "100",
    "price_drop_interval_minutes": 60,
    "reserve_price": "6000",
}


def _flag(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    monkeypatch.setattr(settings, "feature_ascending_auction", enabled)


def _create(
    client: TestClient,
    seller: AuthenticatedUser,
    *,
    start_in: timedelta = -timedelta(minutes=1),
    **extra,
):
    item = create_item(client, seller, starting_price=str(START))
    start = datetime.now(UTC) + start_in
    return client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item["id"],
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(days=3)).isoformat(),
            "minimum_bid_increment": "100",
            **extra,
        },
    )


def _expire(db: Session, auction_id: int) -> None:
    db.expire_all()
    auction = db.get(Auction, auction_id)
    auction.end_time = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()


@pytest.fixture
def seller(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="seller@example.com")


@pytest.mark.parametrize("enabled", [True, False])
def test_features_endpoint_reflects_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    _flag(monkeypatch, enabled)
    response = client.get("/api/v1/features")
    assert response.status_code == 200
    assert response.json() == {"ascending_auction": enabled}


def test_default_setting_is_disabled() -> None:
    assert settings.__class__(_env_file=None).feature_ascending_auction is False


# --- Yaratish ----------------------------------------------------------------


@pytest.mark.parametrize("explicit", [False, True])
def test_disabled_rejects_new_ascending_auction(
    client: TestClient,
    seller: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
    explicit: bool,
) -> None:
    _flag(monkeypatch, False)
    extra = {"pricing_mode": "ascending"} if explicit else {}  # default rejim ham o'suvchi
    response = _create(client, seller, **extra)
    assert response.status_code == 409
    assert response.json()["detail"] == ASCENDING_DISABLED


def test_enabled_creates_ascending_auction(
    client: TestClient, seller: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    _flag(monkeypatch, True)
    response = _create(client, seller)
    assert response.status_code == 201, response.text
    assert response.json()["pricing_mode"] == "ascending"


@pytest.mark.parametrize("enabled", [True, False])
def test_descending_auction_unaffected(
    client: TestClient,
    seller: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    _flag(monkeypatch, enabled)
    created = _create(client, seller, **DESCENDING)
    assert created.status_code == 201, created.text
    buyer = create_user(client, db_session, email="buyer@example.com")
    bought = client.post(f"/api/v1/auctions/{created.json()['id']}/buy-now", headers=buyer.headers)
    assert bought.status_code == 200, bought.text
    assert bought.json()["status"] == "ended"


@pytest.mark.parametrize("enabled", [True, False])
def test_offer_marketplace_unaffected(
    client: TestClient,
    seller: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
) -> None:
    _flag(monkeypatch, enabled)
    item = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={"title": "Samsung Galaxy A55", "condition": "new", "starting_price": "350000000"},
    ).json()
    published = client.post(
        f"/api/v1/items/{item['id']}/publish", headers=seller.headers, json={"duration_days": 5}
    )
    assert published.status_code == 200, published.text
    buyer = create_user(client, db_session, email="buyer@example.com")
    offer = client.post(
        f"/api/v1/items/{item['id']}/offers",
        headers=buyer.headers,
        json={"quantity": 1, "unit_price": "320000000"},
    )
    assert offer.status_code == 201, offer.text


# --- Mavjud o'suvchi auksionlar o'z qoidasida tugaydi ---------------------------


def test_existing_ascending_auction_completes_when_disabled(
    client: TestClient,
    seller: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _flag(monkeypatch, True)
    auction = _create(client, seller).json()
    _flag(monkeypatch, False)

    bidder = create_user(client, db_session, email="bidder@example.com")
    assert client.get(f"/api/v1/auctions/{auction['id']}").status_code == 200
    create_bid(client, bidder, auction["id"], amount=str(START + 100))
    assert client.get(f"/api/v1/auctions/{auction['id']}/bids").status_code == 200

    _expire(db_session, auction["id"])
    close_due_auctions(db_session)
    closed = client.get(f"/api/v1/auctions/{auction['id']}").json()
    assert closed["status"] == "ended"
    assert closed["winner_id"] == bidder.id


def test_existing_ascending_dutch_fallback_still_runs_when_disabled(
    client: TestClient,
    seller: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sotuvchi oldindan rozi bo'lgan fallback bayroq o'chganda ham bajariladi."""
    _flag(monkeypatch, True)
    auction = _create(client, seller, dutch_fallback_floor="6000").json()
    _flag(monkeypatch, False)

    _expire(db_session, auction["id"])
    close_due_auctions(db_session)
    db_session.expire_all()
    old = db_session.get(Auction, auction["id"])
    assert old.status == AuctionStatus.ENDED
    assert old.continued_as_auction_id is not None
    continuation = db_session.get(Auction, old.continued_as_auction_id)
    assert continuation.pricing_mode == PricingMode.DESCENDING


# --- Narx rejimini o'zgartirish (rejalashtirilgan) --------------------------------


def test_disabled_blocks_switch_to_ascending(
    client: TestClient, seller: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    _flag(monkeypatch, False)
    auction = _create(client, seller, start_in=timedelta(minutes=10), **DESCENDING).json()
    response = client.patch(
        f"/api/v1/auctions/{auction['id']}/pricing",
        headers=seller.headers,
        json={"pricing_mode": "ascending"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == ASCENDING_DISABLED


def test_disabled_existing_scheduled_ascending_keeps_its_rules(
    client: TestClient, seller: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Allaqachon o'suvchi bo'lgan auksion tahrirlanadi; pasayuvchiga o'tish ham mumkin."""
    _flag(monkeypatch, True)
    auction = _create(client, seller, start_in=timedelta(minutes=10)).json()
    _flag(monkeypatch, False)
    url = f"/api/v1/auctions/{auction['id']}/pricing"

    keep = client.patch(
        url, headers=seller.headers, json={"pricing_mode": "ascending", "buy_now_price": "15000"}
    )
    assert keep.status_code == 200, keep.text
    to_dutch = client.patch(url, headers=seller.headers, json=DESCENDING)
    assert to_dutch.status_code == 200, to_dutch.text
    back = client.patch(url, headers=seller.headers, json={"pricing_mode": "ascending"})
    assert back.status_code == 409


# --- Qayta joylash ----------------------------------------------------------------


def _unsold_ascending(client, seller, db_session, monkeypatch) -> dict:
    _flag(monkeypatch, True)
    auction = _create(client, seller).json()
    _expire(db_session, auction["id"])
    close_due_auctions(db_session)
    return auction


def test_disabled_relist_as_ascending_rejected_descending_allowed(
    client: TestClient,
    seller: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auction = _unsold_ascending(client, seller, db_session, monkeypatch)
    _flag(monkeypatch, False)
    url = f"/api/v1/auctions/{auction['id']}/relist"

    as_ascending = client.post(
        url, headers=seller.headers, json={"duration_days": 5, "starting_price": "9000"}
    )
    assert as_ascending.status_code == 409
    assert as_ascending.json()["detail"] == ASCENDING_DISABLED

    as_descending = client.post(
        url,
        headers=seller.headers,
        json={"duration_days": 5, "starting_price": "9000", **DESCENDING},
    )
    assert as_descending.status_code == 201, as_descending.text
    assert as_descending.json()["pricing_mode"] == "descending"


def test_enabled_relist_as_ascending_works(
    client: TestClient,
    seller: AuthenticatedUser,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auction = _unsold_ascending(client, seller, db_session, monkeypatch)
    response = client.post(
        f"/api/v1/auctions/{auction['id']}/relist",
        headers=seller.headers,
        json={"duration_days": 5, "starting_price": "9000"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["pricing_mode"] == "ascending"
