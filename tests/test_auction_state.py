"""Auksion state machine: qo'lda holat o'zgartirish teshigini yopish.

Audit topilmasi: PATCH /auctions/{id}/status sotuvchiga ISTALGAN holatni
yozishga ruxsat berardi. Sotuvchi jonli auksionni `ended` qilib deal/g'olib
oqimini chetlab o'tishi, yoki bidli auksionni `cancelled` qilib bidlarni
kuydirishi mumkin edi.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.models.enums import AuctionStatus
from app.services.auction_state import (
    InvalidAuctionTransition,
    assert_transition,
)


def _register_and_login(client: TestClient, email: str) -> str:
    password = "Password1"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": email.split("@")[0]},
    )
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def _create_active_auction(client: TestClient, seller_token: str) -> int:
    headers = {"Authorization": f"Bearer {seller_token}"}
    item = client.post(
        "/api/v1/items",
        headers=headers,
        json={"title": "Drill", "condition": "used", "starting_price": "100000"},
    )
    assert item.status_code == 201
    now = datetime.now(UTC)
    auction = client.post(
        "/api/v1/auctions",
        headers=headers,
        json={
            "item_id": item.json()["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "10000",
        },
    )
    assert auction.status_code == 201
    return auction.json()["id"]


# --- Sof state machine birligi ---------------------------------------------


def test_allowed_transitions_pass() -> None:
    assert_transition(AuctionStatus.SCHEDULED, AuctionStatus.ACTIVE)
    assert_transition(AuctionStatus.SCHEDULED, AuctionStatus.CANCELLED)
    assert_transition(AuctionStatus.ACTIVE, AuctionStatus.ENDED)
    assert_transition(AuctionStatus.ACTIVE, AuctionStatus.RESERVE_NOT_MET)
    assert_transition(AuctionStatus.ACTIVE, AuctionStatus.CANCELLED)


def test_forbidden_transitions_raise() -> None:
    # Yakuniy holatdan chiqib bo'lmaydi.
    for bad in [
        (AuctionStatus.ENDED, AuctionStatus.ACTIVE),
        (AuctionStatus.CANCELLED, AuctionStatus.ACTIVE),
        (AuctionStatus.ACTIVE, AuctionStatus.SCHEDULED),
        (AuctionStatus.ENDED, AuctionStatus.RESERVE_NOT_MET),
    ]:
        try:
            assert_transition(*bad)
            raise AssertionError(f"{bad} taqiqlanishi kerak edi")
        except InvalidAuctionTransition:
            pass


# --- Endpoint orqali teshik yopilgani ---------------------------------------


def test_seller_cannot_manually_end_auction(client: TestClient) -> None:
    """Sotuvchi jonli auksionni `ended` qila olmaydi (deal oqimini chetlab o'tish)."""
    seller_token = _register_and_login(client, "seller@example.com")
    auction_id = _create_active_auction(client, seller_token)

    response = client.patch(
        f"/api/v1/auctions/{auction_id}/status",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"status": "ended"},
    )
    assert response.status_code == 403


def test_seller_cannot_set_reserve_not_met(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    auction_id = _create_active_auction(client, seller_token)

    response = client.patch(
        f"/api/v1/auctions/{auction_id}/status",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"status": "reserve_not_met"},
    )
    assert response.status_code == 403


def test_seller_cannot_cancel_auction_with_bids(client: TestClient) -> None:
    """Bid tushgach bekor qilib bo'lmaydi — bidlar kuymaydi."""
    seller_token = _register_and_login(client, "seller@example.com")
    bidder_token = _register_and_login(client, "bidder@example.com")
    auction_id = _create_active_auction(client, seller_token)

    bid = client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amount": "110000"},
    )
    assert bid.status_code == 201

    response = client.patch(
        f"/api/v1/auctions/{auction_id}/status",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"status": "cancelled"},
    )
    assert response.status_code == 409

    # Auksion hali ham faol — bid saqlanib qoldi.
    check = client.get(f"/api/v1/auctions/{auction_id}")
    assert check.json()["status"] == "active"


def test_seller_can_cancel_auction_without_bids(client: TestClient) -> None:
    """Bidsiz auksionni bekor qilish qonuniy."""
    seller_token = _register_and_login(client, "seller@example.com")
    auction_id = _create_active_auction(client, seller_token)

    response = client.patch(
        f"/api/v1/auctions/{auction_id}/status",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"status": "cancelled"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_non_seller_cannot_change_status(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    other_token = _register_and_login(client, "other@example.com")
    auction_id = _create_active_auction(client, seller_token)

    response = client.patch(
        f"/api/v1/auctions/{auction_id}/status",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"status": "cancelled"},
    )
    assert response.status_code == 403


def test_closing_already_ended_auction_conflicts(client: TestClient) -> None:
    """Yopilgan auksionni qayta yopib bo'lmaydi (idempotentlik/xavfsizlik)."""
    seller_token = _register_and_login(client, "seller@example.com")
    bidder_token = _register_and_login(client, "bidder@example.com")
    auction_id = _create_active_auction(client, seller_token)

    client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amount": "110000"},
    )
    first = client.post(
        f"/api/v1/auctions/{auction_id}/close",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "ended"

    second = client.post(
        f"/api/v1/auctions/{auction_id}/close",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert second.status_code == 409


# --- E'lonni bekor qilish (DELETE /items/{id}) auksion bilan birga ----------
#
# Ilgari DELETE /items faqat item.status yozardi: jonli auksion bid qabul
# qilishda davom etardi va bidli lotni ham "bekor qilish" mumkin edi.


def test_cancel_listing_cancels_live_auction_without_bids(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    headers = {"Authorization": f"Bearer {seller_token}"}
    auction_id = _create_active_auction(client, seller_token)
    item_id = client.get(f"/api/v1/auctions/{auction_id}").json()["item_id"]

    response = client.delete(f"/api/v1/items/{item_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert client.get(f"/api/v1/auctions/{auction_id}").json()["status"] == "cancelled"


def test_cancel_listing_with_bids_conflicts_and_keeps_auction(client: TestClient) -> None:
    """Bid tushgan lotni e'lon orqali ham bekor qilib bo'lmaydi."""
    seller_token = _register_and_login(client, "seller@example.com")
    bidder_token = _register_and_login(client, "bidder@example.com")
    auction_id = _create_active_auction(client, seller_token)
    item_id = client.get(f"/api/v1/auctions/{auction_id}").json()["item_id"]
    bid = client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amount": "110000"},
    )
    assert bid.status_code == 201

    response = client.delete(
        f"/api/v1/items/{item_id}", headers={"Authorization": f"Bearer {seller_token}"}
    )
    assert response.status_code == 409
    assert client.get(f"/api/v1/auctions/{auction_id}").json()["status"] == "active"
    assert client.get(f"/api/v1/items/{item_id}").json()["status"] != "cancelled"


def test_cancel_listing_after_auction_ended_conflicts(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    bidder_token = _register_and_login(client, "bidder@example.com")
    headers = {"Authorization": f"Bearer {seller_token}"}
    auction_id = _create_active_auction(client, seller_token)
    item_id = client.get(f"/api/v1/auctions/{auction_id}").json()["item_id"]
    client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amount": "110000"},
    )
    assert client.post(f"/api/v1/auctions/{auction_id}/close", headers=headers).status_code == 200

    response = client.delete(f"/api/v1/items/{item_id}", headers=headers)
    assert response.status_code == 409


def test_cancel_listing_without_auction(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    headers = {"Authorization": f"Bearer {seller_token}"}
    item = client.post(
        "/api/v1/items",
        headers=headers,
        json={"title": "Drill", "condition": "used", "starting_price": "100000"},
    )
    assert item.status_code == 201

    response = client.delete(f"/api/v1/items/{item.json()['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_other_user_cannot_cancel_listing(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    other_token = _register_and_login(client, "other@example.com")
    auction_id = _create_active_auction(client, seller_token)
    item_id = client.get(f"/api/v1/auctions/{auction_id}").json()["item_id"]

    response = client.delete(
        f"/api/v1/items/{item_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403
    assert client.get(f"/api/v1/auctions/{auction_id}").json()["status"] == "active"
