"""Faza E2.1: bid, taklif, e'lon va xarid uchun telefon tasdig'i majburiy.

Kelishuvda ikkinchi tomonga telefon ochiladi — tasdiqlanmagan raqam soxta yoki begona
bo'lishi mumkin. Bu testlar talabni tasdiqlanmagan foydalanuvchi bilan tekshiradi
(`unverified_phones`); qolgan korpusda foydalanuvchilar avtomatik tasdiqlanadi (conftest).
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.dependencies import PHONE_VERIFICATION_REQUIRED
from app.models.user import User
from tests.conftest import AuthenticatedUser, create_auction, create_item, create_user


def _verify(db_session: Session, user: AuthenticatedUser, phone: str) -> None:
    row = db_session.get(User, user.id)
    row.phone = phone
    row.phone_verified_at = datetime.now(UTC)
    db_session.commit()


def _assert_gated(response) -> None:
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == PHONE_VERIFICATION_REQUIRED


@pytest.fixture
def parties(client: TestClient, db_session: Session, unverified_phones: None):
    """Tasdiqlangan sotuvchi + tasdiqlanmagan xaridor."""
    seller = create_user(client, db_session, email="seller@example.com")
    _verify(db_session, seller, "+998901000001")
    buyer = create_user(client, db_session, email="buyer@example.com")
    return seller, buyer


def test_unverified_user_cannot_create_listing(
    client: TestClient, db_session: Session, unverified_phones: None
) -> None:
    user = create_user(client, db_session, email="u@example.com")
    response = client.post(
        "/api/v1/items",
        headers=user.headers,
        json={"title": "iPhone 13", "condition": "used", "starting_price": "500000000"},
    )
    _assert_gated(response)


def test_phone_without_verification_is_not_enough(
    client: TestClient, db_session: Session, unverified_phones: None
) -> None:
    """Profilga raqam yozish yetmaydi — OTP tasdig'i kerak."""
    user = create_user(client, db_session, email="u@example.com")
    client.patch("/api/v1/users/me", headers=user.headers, json={"phone": "+998901234567"})
    response = client.post(
        "/api/v1/items",
        headers=user.headers,
        json={"title": "iPhone 13", "condition": "used", "starting_price": "500000000"},
    )
    _assert_gated(response)


def test_unverified_user_cannot_bid_or_buy_now(client: TestClient, parties) -> None:
    seller, buyer = parties
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])

    _assert_gated(
        client.post(f"/api/v1/bids/{auction['id']}", headers=buyer.headers, json={"amount": "1100"})
    )
    _assert_gated(
        client.post(
            f"/api/v1/auctions/{auction['id']}/bids", headers=buyer.headers, json={"amount": "1100"}
        )
    )
    _assert_gated(client.post(f"/api/v1/auctions/{auction['id']}/buy-now", headers=buyer.headers))


def test_unverified_user_cannot_make_offer(client: TestClient, parties) -> None:
    seller, buyer = parties
    item = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={
            "title": "Qishki shina 205/55 R16",
            "condition": "new",
            "starting_price": "60000000",
            "quantity": 4,
        },
    ).json()
    response = client.post(
        f"/api/v1/items/{item['id']}/offers",
        headers=buyer.headers,
        json={"quantity": 2, "unit_price": "55000000"},
    )
    _assert_gated(response)


def test_verified_user_can_bid(client: TestClient, db_session: Session, parties) -> None:
    seller, buyer = parties
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    _verify(db_session, buyer, "+998901000002")
    response = client.post(
        f"/api/v1/bids/{auction['id']}", headers=buyer.headers, json={"amount": "1100"}
    )
    assert response.status_code == 201, response.text
