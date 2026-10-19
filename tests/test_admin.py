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


def _set_role(db_session: Session, email: str, role: UserRole) -> None:
    user_repository = UserRepository(db_session)
    user = user_repository.get_by_email(email)
    assert user is not None
    user_repository.set_role(user, role)


def _make_admin(db_session: Session, email: str) -> None:
    _set_role(db_session, email, UserRole.ADMIN)


def _make_superadmin(db_session: Session, email: str) -> None:
    _set_role(db_session, email, UserRole.SUPERADMIN)


def _create_item(client: TestClient, seller_token: str, title: str = "Bench vise") -> dict:
    response = client.post(
        "/api/v1/items",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"title": title, "condition": "used", "starting_price": "4000"},
    )
    assert response.status_code == 201
    return response.json()


def _create_auction(client: TestClient, seller_token: str, item_id: int) -> dict:
    now = datetime.now(UTC)
    response = client.post(
        "/api/v1/auctions",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "item_id": item_id,
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "500",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_admin_endpoints_and_permissions(client: TestClient, db_session: Session) -> None:
    admin_token = _register_and_login(client, "admin@example.com")
    seller_token = _register_and_login(client, "seller@example.com")
    buyer_token = _register_and_login(client, "buyer@example.com")
    _make_admin(db_session, "admin@example.com")

    non_admin_response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert non_admin_response.status_code == 403

    users_response = client.get(
        "/api/v1/admin/users?search=seller&limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert users_response.status_code == 200
    seller_user = next(
        user for user in users_response.json() if user["email"] == "seller@example.com"
    )

    block_response = client.post(
        f"/api/v1/admin/users/{seller_user['id']}/block",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert block_response.status_code == 200
    assert block_response.json()["is_active"] is False

    unblock_response = client.post(
        f"/api/v1/admin/users/{seller_user['id']}/unblock",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert unblock_response.status_code == 200
    assert unblock_response.json()["is_active"] is True

    # Rol berish faqat superadminga ochiq — oddiy admin 403 oladi.
    admin_role_response = client.patch(
        f"/api/v1/admin/users/{seller_user['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "seller"},
    )
    assert admin_role_response.status_code == 403

    superadmin_token = _register_and_login(client, "root@example.com")
    _make_superadmin(db_session, "root@example.com")
    role_response = client.patch(
        f"/api/v1/admin/users/{seller_user['id']}/role",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={"role": "seller"},
    )
    assert role_response.status_code == 200
    assert role_response.json()["role"] == "seller"

    item = _create_item(client, seller_token)
    items_response = client.get(
        "/api/v1/admin/items?search=vise&status=draft",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert items_response.status_code == 200
    assert [entry["id"] for entry in items_response.json()] == [item["id"]]

    approve_response = client.post(
        f"/api/v1/admin/items/{item['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "active"

    reject_response = client.post(
        f"/api/v1/admin/items/{item['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "cancelled"

    auction_item = _create_item(client, seller_token, title="Auction item")
    auction = _create_auction(client, seller_token, auction_item["id"])

    bid_response = client.post(
        f"/api/v1/bids/{auction['id']}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"amount": "4500"},
    )
    assert bid_response.status_code == 201

    bids_response = client.get(
        f"/api/v1/admin/bids?auction_id={auction['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert bids_response.status_code == 200
    assert [entry["id"] for entry in bids_response.json()] == [bid_response.json()["id"]]

    auctions_response = client.get(
        "/api/v1/admin/auctions?status=active",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert auctions_response.status_code == 200
    assert auction["id"] in [entry["id"] for entry in auctions_response.json()]

    cancel_response = client.post(
        f"/api/v1/admin/auctions/{auction['id']}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_superadmin_privileges_and_protections(client: TestClient, db_session: Session) -> None:
    admin_token = _register_and_login(client, "admin@example.com")
    _register_and_login(client, "admin2@example.com")
    superadmin_token = _register_and_login(client, "root@example.com")
    _register_and_login(client, "victim@example.com")
    _make_admin(db_session, "admin@example.com")
    _make_admin(db_session, "admin2@example.com")
    _make_superadmin(db_session, "root@example.com")

    def user_id(email: str) -> int:
        user = UserRepository(db_session).get_by_email(email)
        assert user is not None
        return user.id

    # Superadmin admin foydalanuvchini oddiy userga tushira oladi.
    demote = client.patch(
        f"/api/v1/admin/users/{user_id('victim@example.com')}/role",
        headers={"Authorization": f"Bearer {superadmin_token}"},
        json={"role": "user"},
    )
    assert demote.status_code == 200
    assert demote.json()["role"] == "user"

    # Oddiy admin boshqa adminni bloklay olmaydi — faqat superadmin.
    admin_blocks_admin = client.post(
        f"/api/v1/admin/users/{user_id('admin2@example.com')}/block",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_blocks_admin.status_code == 403

    superadmin_blocks_admin = client.post(
        f"/api/v1/admin/users/{user_id('admin2@example.com')}/block",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert superadmin_blocks_admin.status_code == 200
    assert superadmin_blocks_admin.json()["is_active"] is False

    # Superadminni hech kim (hatto boshqa superadmin ham) bloklay olmaydi.
    block_superadmin = client.post(
        f"/api/v1/admin/users/{user_id('root@example.com')}/block",
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert block_superadmin.status_code == 403


def test_admin_can_view_orders_and_statistics(client: TestClient, db_session: Session) -> None:
    admin_token = _register_and_login(client, "admin@example.com")
    seller_token = _register_and_login(client, "seller@example.com")
    buyer_token = _register_and_login(client, "buyer@example.com")
    _make_admin(db_session, "admin@example.com")

    item = _create_item(client, seller_token, title="Deal item")
    auction = _create_auction(client, seller_token, item["id"])

    bid_response = client.post(
        f"/api/v1/bids/{auction['id']}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"amount": "4500"},
    )
    assert bid_response.status_code == 201

    close_response = client.post(
        f"/api/v1/auctions/{auction['id']}/close",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    assert close_response.status_code == 200

    orders_response = client.get(
        "/api/v1/admin/deals?status=agreed",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert orders_response.status_code == 200
    assert len(orders_response.json()) == 1

    stats_response = client.get(
        "/api/v1/admin/statistics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total_users"] == 3
    assert stats["total_completed_deals"] == 0
    assert stats["total_sales_amount"] == "0"
