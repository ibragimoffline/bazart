"""UI uchun qo'shilgan o'qish maydonlari/endpointlari.

- `AuctionRead.minimum_next_bid` — server qabul qiladigan minimum (frontend
  qadam jadvalini takrorlamaydi).
- `GET /auctions/{id}/bids` — ochiq bid tarixi: ism maskalangan, proxy max yo'q.
- `GET /users/me` — `phone_verified_at` faqat egaga.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.region import District, Region
from app.models.user import User
from tests.conftest import create_auction, create_bid, create_item, create_user


def test_minimum_next_bid_uses_seller_step_when_tiers_disabled(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"], minimum_bid_increment="100")
    assert auction["minimum_next_bid"] == str(int(auction["current_price"]) + 100)


def test_minimum_next_bid_uses_tier_step(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "tiered_bid_increment_enabled", True)
    seller = create_user(client, db_session, email="seller@example.com")
    item = create_item(client, seller, starting_price="1000")
    auction = create_auction(client, seller, item["id"], minimum_bid_increment="100")
    # < 100 000 so'm narxda jadval qadami 5 000 so'm = 500 000 tiyin.
    assert auction["minimum_next_bid"] == str(int(auction["current_price"]) + 500_000)


def test_bid_history_is_public_and_masked(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    bidder = create_user(client, db_session, email="alisher@example.com")
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    create_bid(client, bidder, auction["id"], amount="1100")
    create_bid(client, bidder, auction["id"], amount="1300")

    response = client.get(f"/api/v1/auctions/{auction['id']}/bids")
    assert response.status_code == 200
    bids = response.json()
    assert [b["amount"] for b in bids] == ["1300", "1100"]
    # conftest full_name = email prefiksi ("alisher") -> "a***r".
    assert bids[0]["bidder_display"] == "a***r"
    assert "max_amount" not in bids[0]
    assert "alisher" not in response.text


def test_bid_history_unknown_auction(client: TestClient) -> None:
    assert client.get("/api/v1/auctions/999999/bids").status_code == 404


@pytest.mark.usefixtures("unverified_phones")
def test_users_me_exposes_phone_verified_at(client: TestClient, db_session: Session) -> None:
    user = create_user(client, db_session, email="me@example.com")
    me = client.get("/api/v1/users/me", headers=user.headers).json()
    assert me["phone_verified_at"] is None


def _regions(db: Session) -> tuple[Region, Region, District]:
    tashkent = Region(code="TAS_CITY", name_uz="Toshkent shahri", name_ru="город Ташкент")
    khorezm = Region(code="XOR", name_uz="Xorazm viloyati", name_ru="Хорезмская область")
    db.add_all([tashkent, khorezm])
    db.flush()
    chilonzor = District(region_id=tashkent.id, name_uz="Chilonzor", name_ru="Чиланзар")
    db.add(chilonzor)
    db.commit()
    return tashkent, khorezm, chilonzor


def _item_payload(**extra: object) -> dict:
    return {
        "title": "Samsung Galaxy S23",
        "condition": "used",
        "starting_price": "350000000",
        **extra,
    }


def test_item_district_must_belong_to_region(client: TestClient, db_session: Session) -> None:
    tashkent, khorezm, chilonzor = _regions(db_session)
    seller = create_user(client, db_session, email="seller@example.com")

    ok = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json=_item_payload(region_id=tashkent.id, district_id=chilonzor.id),
    )
    assert ok.status_code == 201

    mismatch = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json=_item_payload(region_id=khorezm.id, district_id=chilonzor.id),
    )
    assert mismatch.status_code == 400

    orphan = client.post(
        "/api/v1/items", headers=seller.headers, json=_item_payload(district_id=chilonzor.id)
    )
    assert orphan.status_code == 400

    unknown = client.post(
        "/api/v1/items", headers=seller.headers, json=_item_payload(region_id=999)
    )
    assert unknown.status_code == 400

    # Qisman yangilash: faqat viloyat o'zgarsa, eski tuman bilan ziddiyat tutiladi.
    patch = client.patch(
        f"/api/v1/items/{ok.json()['id']}", headers=seller.headers, json={"region_id": khorezm.id}
    )
    assert patch.status_code == 400


@pytest.mark.usefixtures("unverified_phones")
def test_profile_phone_is_normalized_and_verified_phone_is_kept(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(client, db_session, email="me@example.com")
    response = client.patch(
        "/api/v1/users/me", headers=user.headers, json={"phone": "+998 90 123-45-67"}
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+998901234567"

    owner = db_session.get(User, user.id)
    owner.phone_verified_at = datetime.now(UTC)
    db_session.commit()

    # Tasdiqlangan raqam PATCH bilan almashtirilmaydi (faqat OTP orqali) — tasdiq saqlanadi.
    swap = client.patch(
        "/api/v1/users/me", headers=user.headers, json={"phone": "+998 91 000 00 00"}
    )
    assert swap.status_code == 409
    me = client.get("/api/v1/users/me", headers=user.headers).json()
    assert me["phone"] == "+998901234567"
    assert me["phone_verified_at"] is not None

    assert (
        client.patch("/api/v1/users/me", headers=user.headers, json={"phone": "abc"}).status_code
        == 422
    )
