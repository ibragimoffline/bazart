"""Ikki tomonlama sharh + sotuvchi reytingi.

Order COMPLETED bo'lgach (hold -> capture) ishtirokchilar bir-birini
baholaydi (1-5 yulduz). Qabul qiluvchining `seller_rating` (o'rtacha) va
`seller_rating_count` UNGA kelgan barcha sharhlardan qayta hisoblanadi.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> tuple[str, int]:
    """Ro'yxatdan o'tkazadi va (token, user_id) qaytaradi."""
    password = "Password1"
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": email.split("@")[0]},
    )
    assert reg.status_code == 201
    login = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"], reg.json()["id"]


def _completed_order(client: TestClient, seller_token: str, buyer_token: str) -> dict:
    """Auksion -> bid -> close -> sotuvchi yakunlaydi orqali COMPLETED order."""
    item = client.post(
        "/api/v1/items",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"title": "Lens", "condition": "used", "starting_price": "10000"},
    )
    assert item.status_code == 201
    now = datetime.now(UTC)
    auction = client.post(
        "/api/v1/auctions",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "item_id": item.json()["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "1000",
        },
    )
    auction_id = auction.json()["id"]
    client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"amount": "12000"},
    )
    client.post(
        f"/api/v1/auctions/{auction_id}/close",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    orders = client.get("/api/v1/orders/buyer", headers={"Authorization": f"Bearer {buyer_token}"})
    order = orders.json()[0]

    # Faza E: to'lov yo'q — sotuvchi order'ni o'zi yakunlaydi (E2 da kelishuv tasdig'i).
    finish = client.patch(
        f"/api/v1/orders/{order['id']}/status",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"status": "completed"},
    )
    assert finish.status_code == 200, finish.text

    done = client.get(
        f"/api/v1/orders/{order['id']}", headers={"Authorization": f"Bearer {buyer_token}"}
    )
    assert done.json()["status"] == "completed"
    return order


def _pending_order(client: TestClient, seller_token: str, buyer_token: str) -> dict:
    """Faqat auksion -> close orqali order (PENDING_PAYMENT, COMPLETED emas)."""
    item = client.post(
        "/api/v1/items",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={"title": "Lens", "condition": "used", "starting_price": "10000"},
    )
    now = datetime.now(UTC)
    auction = client.post(
        "/api/v1/auctions",
        headers={"Authorization": f"Bearer {seller_token}"},
        json={
            "item_id": item.json()["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(days=1)).isoformat(),
            "minimum_bid_increment": "1000",
        },
    )
    auction_id = auction.json()["id"]
    client.post(
        f"/api/v1/bids/{auction_id}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        json={"amount": "12000"},
    )
    client.post(
        f"/api/v1/auctions/{auction_id}/close",
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    orders = client.get("/api/v1/orders/buyer", headers={"Authorization": f"Bearer {buyer_token}"})
    return orders.json()[0]


def test_buyer_reviews_seller_updates_rating(client: TestClient) -> None:
    seller, seller_id = _register_and_login(client, "seller@example.com")
    buyer, _ = _register_and_login(client, "buyer@example.com")
    order = _completed_order(client, seller, buyer)

    resp = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"order_id": order["id"], "stars": 5, "text": "Zo'r sotuvchi"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["stars"] == 5
    assert body["to_id"] == seller_id

    # Sotuvchi reytingi yangilandi.
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {seller}"})
    assert me.json()["seller_rating"] == 5.0
    assert me.json()["seller_rating_count"] == 1


def test_duplicate_review_conflicts(client: TestClient) -> None:
    seller, _ = _register_and_login(client, "seller@example.com")
    buyer, _ = _register_and_login(client, "buyer@example.com")
    order = _completed_order(client, seller, buyer)

    first = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"order_id": order["id"], "stars": 5},
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"order_id": order["id"], "stars": 4},
    )
    assert second.status_code == 409


def test_review_on_non_completed_order_400(client: TestClient) -> None:
    seller, _ = _register_and_login(client, "seller@example.com")
    buyer, _ = _register_and_login(client, "buyer@example.com")
    order = _pending_order(client, seller, buyer)

    resp = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"order_id": order["id"], "stars": 5},
    )
    assert resp.status_code == 400


def test_non_participant_forbidden(client: TestClient) -> None:
    seller, _ = _register_and_login(client, "seller@example.com")
    buyer, _ = _register_and_login(client, "buyer@example.com")
    intruder, _ = _register_and_login(client, "intruder@example.com")
    order = _completed_order(client, seller, buyer)

    resp = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {intruder}"},
        json={"order_id": order["id"], "stars": 5},
    )
    assert resp.status_code == 403


def test_stars_out_of_range_422(client: TestClient) -> None:
    seller, _ = _register_and_login(client, "seller@example.com")
    buyer, _ = _register_and_login(client, "buyer@example.com")
    order = _completed_order(client, seller, buyer)

    resp = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"order_id": order["id"], "stars": 6},
    )
    assert resp.status_code == 422


def test_average_of_two_reviews(client: TestClient) -> None:
    """Sotuvchi ikki orderda 5 va 4 baho oladi -> o'rtacha 4.5, count 2."""
    seller, seller_id = _register_and_login(client, "seller@example.com")
    buyer1, _ = _register_and_login(client, "buyer1@example.com")
    buyer2, _ = _register_and_login(client, "buyer2@example.com")

    order1 = _completed_order(client, seller, buyer1)
    order2 = _completed_order(client, seller, buyer2)

    r1 = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer1}"},
        json={"order_id": order1["id"], "stars": 5},
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer2}"},
        json={"order_id": order2["id"], "stars": 4},
    )
    assert r2.status_code == 201

    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {seller}"})
    assert me.json()["seller_rating"] == 4.5
    assert me.json()["seller_rating_count"] == 2

    # Foydalanuvchiga kelgan sharhlar ro'yxati.
    listed = client.get(f"/api/v1/reviews/user/{seller_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 2


def test_list_user_reviews_returns_reviews(client: TestClient) -> None:
    seller, seller_id = _register_and_login(client, "seller@example.com")
    buyer, _ = _register_and_login(client, "buyer@example.com")
    order = _completed_order(client, seller, buyer)

    client.post(
        "/api/v1/reviews",
        headers={"Authorization": f"Bearer {buyer}"},
        json={"order_id": order["id"], "stars": 3, "text": "Yaxshi"},
    )
    resp = client.get(f"/api/v1/reviews/user/{seller_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["stars"] == 3
    assert body[0]["to_id"] == seller_id
    assert body[0]["text"] == "Yaxshi"
