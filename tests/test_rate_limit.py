"""Rate limiting testlari.

Mavjud test to'plami "test" muhitida ishlaydi va limiter o'chiq bo'ladi (aks
holda ko'p login/bid qiluvchi testlar 429 olardi). Bu yerdagi testlar
limiter'ni ATAYLAB yoqadi: muhitni "local" ga o'zgartiradi, kichik limit
qo'yadi va har test boshida hisoblagichni tozalaydi.
"""

from conftest import (
    TEST_PASSWORD,
    AuthenticatedUser,
    create_auction,
    create_item,
    create_user,
    freeze_rate_limit_window,
    register_user,
)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import reset_rate_limits
from app.models.enums import UserRole


def _enable_limiter(monkeypatch) -> None:
    """Limiter'ni yoqadi: NON-test muhit + rate_limit_enabled=True."""
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    freeze_rate_limit_window(monkeypatch)


def test_login_under_limit_ok_then_over_limit_429(
    client: TestClient,
    monkeypatch,
) -> None:
    """Limitgacha loginlar o'tadi; limitdan oshgani 429 oladi."""
    _enable_limiter(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_login_per_minute", 3)
    reset_rate_limits()

    # register /register scope'iga tegishli — login hisobiga kirmaydi.
    register_user(client, email="ratelimit-login@example.com")
    credentials = {"username": "ratelimit-login@example.com", "password": TEST_PASSWORD}

    # Limitgacha (3 ta) muvaffaqiyatli login.
    for _ in range(3):
        response = client.post("/api/v1/auth/login", data=credentials)
        assert response.status_code == 200

    # 4-urinish limitdan oshadi.
    response = client.post("/api/v1/auth/login", data=credentials)
    assert response.status_code == 429


def test_login_limiter_disabled_in_test_env(
    client: TestClient,
    monkeypatch,
) -> None:
    """Muhit "test" bo'lsa limiter no-op: limitdan ko'p login ham 429 bermaydi."""
    # Muhit "test" (conftest default) — faqat rate_limit_enabled yoqamiz.
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_per_minute", 2)
    reset_rate_limits()

    register_user(client, email="ratelimit-off@example.com")
    credentials = {"username": "ratelimit-off@example.com", "password": TEST_PASSWORD}

    for _ in range(5):
        response = client.post("/api/v1/auth/login", data=credentials)
        assert response.status_code == 200


def _setup_bid_context(
    client: TestClient,
    db_session: Session,
) -> tuple[AuthenticatedUser, int]:
    """Limiter hali o'chiq (test muhit)ligicha bidder + auksion tayyorlaydi."""
    seller = create_user(
        client, db_session, email="ratelimit-seller@example.com", role=UserRole.SELLER
    )
    bidder = create_user(client, db_session, email="ratelimit-bidder@example.com")
    item = create_item(client, seller)
    auction = create_auction(client, seller, item["id"])
    return bidder, auction["id"]


def test_bid_over_limit_429(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    """Limitdan oshgan bid 429 oladi.

    Bid semantikasi (201/400/...) bu yerda muhim emas — 429 endpoint
    mantig'idan OLDIN, dependency bosqichida ishga tushadi. Shuning uchun bid
    to'g'ri yoki noto'g'ri bo'lishidan qat'i nazar, limit oshsa 429 keladi.
    """
    # Kontekstni limiter o'chiq (test muhit) holida tayyorlaymiz: setup
    # ichidagi login/register 429 ga tushib qolmasin.
    bidder, auction_id = _setup_bid_context(client, db_session)

    _enable_limiter(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_bid_per_minute", 3)
    reset_rate_limits()

    statuses = []
    for i in range(5):
        response = client.post(
            f"/api/v1/bids/{auction_id}",
            headers=bidder.headers,
            json={"amount": str(1100 + i * 100)},
        )
        statuses.append(response.status_code)

    # Limit=3: 1-3 urinish limiter'dan o'tadi (endpoint javobi qanday bo'lsa
    # ham), 4-urinishdan boshlab 429.
    assert 429 in statuses
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_bid_over_limit_429_on_auctions_route(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    """Ikkinchi bid route (/auctions/{id}/bids) ham "bid" scope bilan himoyalangan."""
    bidder, auction_id = _setup_bid_context(client, db_session)

    _enable_limiter(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_bid_per_minute", 3)
    reset_rate_limits()

    statuses = []
    for i in range(5):
        response = client.post(
            f"/api/v1/auctions/{auction_id}/bids",
            headers=bidder.headers,
            json={"amount": str(1100 + i * 100)},
        )
        statuses.append(response.status_code)

    assert statuses[3] == 429
    assert statuses[4] == 429
