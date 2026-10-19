from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository


def _register_and_login(client: TestClient, email: str) -> str:
    password = "Password1"
    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": email.split("@")[0]},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def _create_closed_auction_order(client: TestClient, seller_token: str, buyer_token: str) -> dict:
    item_response = client.post(
        "/api/v1/items",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "title": "Router table",
            "condition": "used",
            "starting_price": "10000",
        },
    )
    assert item_response.status_code == 201

    now = datetime.now(UTC)
    auction_response = client.post(
        "/api/v1/auctions",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "item_id": item_response.json()["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "1000",
        },
    )
    assert auction_response.status_code == 201
    auction_id = auction_response.json()["id"]

    bid_response = client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"amount": "12000"},
    )
    assert bid_response.status_code == 201

    close_response = client.post(
        f"/api/v1/auctions/{auction_id}/close",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert close_response.status_code == 200

    buyer_orders_response = client.get(
        "/api/v1/deals/buyer",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert buyer_orders_response.status_code == 200
    deals = buyer_orders_response.json()
    assert len(deals) == 1
    return deals[0]


def test_order_creation_after_auction_close_and_role_views(
    client: TestClient,
    db_session: Session,
) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    buyer_token = _register_and_login(client, "buyer@example.com")
    admin_token = _register_and_login(client, "admin@example.com")

    admin_user = UserRepository(db_session).get_by_email("admin@example.com")
    assert admin_user is not None
    UserRepository(db_session).set_role(admin_user, UserRole.ADMIN)

    deal = _create_closed_auction_order(client, seller_token, buyer_token)
    assert deal["final_price"] == "12000"
    assert deal["status"] == "agreed"

    buyer_orders_response = client.get(
        "/api/v1/deals/buyer",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert buyer_orders_response.status_code == 200
    assert [entry["id"] for entry in buyer_orders_response.json()] == [deal["id"]]

    seller_orders_response = client.get(
        "/api/v1/deals/seller",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert seller_orders_response.status_code == 200
    assert [entry["id"] for entry in seller_orders_response.json()] == [deal["id"]]

    admin_orders_response = client.get(
        "/api/v1/deals/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_orders_response.status_code == 200
    assert [entry["id"] for entry in admin_orders_response.json()] == [deal["id"]]

    marked = client.post(
        f"/api/v1/deals/{deal['id']}/complete",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert marked.status_code == 200
    assert marked.json()["status"] == "agreed"
    assert marked.json()["seller_marked_sold_at"] is not None

    confirmed = client.post(
        f"/api/v1/deals/{deal['id']}/confirm",
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "completed"
    assert confirmed.json()["completed_at"] is not None


def test_unauthorized_user_cannot_view_or_manage_another_users_order(client: TestClient) -> None:
    seller_token = _register_and_login(client, "seller@example.com")
    buyer_token = _register_and_login(client, "buyer@example.com")
    stranger_token = _register_and_login(client, "stranger@example.com")

    deal = _create_closed_auction_order(client, seller_token, buyer_token)

    read_response = client.get(
        f"/api/v1/deals/{deal['id']}",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert read_response.status_code == 403

    # Xaridor "Sotildi" belgilay olmaydi, begona umuman ko'rmaydi (404).
    assert (
        client.post(
            f"/api/v1/deals/{deal['id']}/complete",
            headers={"Authorization": f"Bearer {buyer_token}"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/deals/{deal['id']}/cancel",
            headers={"Authorization": f"Bearer {stranger_token}"},
            json={"reason": "other"},
        ).status_code
        == 404
    )
