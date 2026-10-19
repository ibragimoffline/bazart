"""Kuzatuv ro'yxati xabarlari: "narx tushdi" (pasayuvchi auksion), "2 soat qoldi",
"sizni ortda qoldirishdi" — va ularning Telegram'ga yetkazilishi (havola bilan).
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.tasks.notifications as notifications_task
from app.core.config import settings
from app.models.auction import Auction
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.user import User
from app.money import dropped_by_at_least
from app.services.ending_soon import notify_ending_soon
from app.services.price_alerts import notify_price_drops
from tests.conftest import AuthenticatedUser, create_bid, create_item, create_user

START = 10_000
STEP = 100
FLOOR = 6_000


class _Recorder:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> bool:
        self.sent.append((chat_id, text))
        return True


def _link_telegram(db: Session, user: AuthenticatedUser, chat_id: str) -> None:
    db.get(User, user.id).telegram_chat_id = chat_id
    db.commit()


def _dutch(client: TestClient, seller: AuthenticatedUser) -> dict:
    item = create_item(client, seller, starting_price=str(START))
    now = datetime.now(UTC)
    resp = client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "duration_days": 3,
            "pricing_mode": "descending",
            "price_decrement": str(STEP),
            "price_drop_interval_minutes": 60,
            "reserve_price": str(FLOOR),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _age(db: Session, auction_id: int, minutes: int) -> None:
    db.expire_all()
    db.get(Auction, auction_id).start_time = datetime.now(UTC) - timedelta(minutes=minutes)
    db.commit()


def _alerts(db: Session) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.type == NotificationType.PRICE_DROPPED)
            .order_by(Notification.id)
        )
    )


def test_dropped_by_at_least() -> None:
    assert dropped_by_at_least(10_000, 9_000, 1000) is True  # aynan 10%
    assert dropped_by_at_least(10_000, 9_001, 1000) is False
    assert dropped_by_at_least(10_000, 10_000, 1000) is False
    with pytest.raises(ValueError):
        dropped_by_at_least(0, 0, 1000)


# --- "Narx tushdi" ----------------------------------------------------------------


def test_price_drop_alerts_watchers_on_meaningful_drops_only(
    client: TestClient, db_session: Session
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    auction = _dutch(client, seller)
    for user in (watcher, seller):
        client.post("/api/v1/watchlist", headers=user.headers, json={"auction_id": auction["id"]})

    _age(db_session, auction["id"], minutes=125)  # 9 800 — atigi 2%
    assert notify_price_drops(db_session) == 0

    _age(db_session, auction["id"], minutes=11 * 60 + 5)  # 8 900 — 11%
    assert notify_price_drops(db_session) == 1
    alerts = _alerts(db_session)
    assert [a.user_id for a in alerts] == [watcher.id]  # sotuvchi o'ziga xabar olmaydi
    assert alerts[0].payload["previous_price"] == str(START)
    assert alerts[0].payload["current_price"] == "8900"
    assert alerts[0].payload["at_floor"] is False

    assert notify_price_drops(db_session) == 0  # takror yo'q
    _age(db_session, auction["id"], minutes=13 * 60 + 5)  # 8 700 — 8 900 dan atigi 2%
    assert notify_price_drops(db_session) == 0

    _age(db_session, auction["id"], minutes=60 * 60)  # chegara 6 000
    assert notify_price_drops(db_session) == 1
    final = _alerts(db_session)[-1]
    assert final.payload["at_floor"] is True
    assert final.payload["previous_price"] == "8900"
    assert "eng past narx" in (final.body or "")
    assert notify_price_drops(db_session) == 0


def test_price_drop_skips_sold_and_ascending(client: TestClient, db_session: Session) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    buyer = create_user(client, db_session, email="buyer@example.com")
    sold = _dutch(client, seller)
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": sold["id"]})
    _age(db_session, sold["id"], minutes=11 * 60 + 5)
    assert client.post(f"/api/v1/auctions/{sold['id']}/buy-now", headers=buyer.headers).is_success

    ascending_item = create_item(client, seller, starting_price=str(START))
    client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": ascending_item["id"],
            "start_time": datetime.now(UTC).isoformat(),
            "duration_days": 3,
        },
    )
    assert notify_price_drops(db_session) == 0
    assert _alerts(db_session) == []


def test_price_drop_reaches_telegram_with_link(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(notifications_task, "get_telegram_provider", lambda: recorder)
    monkeypatch.setattr(settings, "public_site_url", "https://bazart.uz/")
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    _link_telegram(db_session, watcher, "chat-1")
    auction = _dutch(client, seller)
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": auction["id"]})
    _age(db_session, auction["id"], minutes=11 * 60 + 5)

    notify_price_drops(db_session)
    assert len(recorder.sent) == 1
    chat, text = recorder.sent[0]
    assert chat == "chat-1"
    assert text.startswith("Narx tushdi")
    assert f"https://bazart.uz/lot/{auction['id']}" in text


# --- "Sizni ortda qoldirishdi" ---------------------------------------------------


def test_outbid_names_lot_and_price_and_reaches_telegram(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = _Recorder()
    monkeypatch.setattr(notifications_task, "get_telegram_provider", lambda: recorder)
    monkeypatch.setattr(settings, "public_site_url", "https://bazart.uz")
    seller = create_user(client, db_session, email="seller@example.com")
    first = create_user(client, db_session, email="first@example.com")
    second = create_user(client, db_session, email="second@example.com")
    _link_telegram(db_session, first, "chat-first")
    item = create_item(client, seller, title="Nikon Z50 kamera", starting_price="1000")
    now = datetime.now(UTC)
    auction = client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "duration_days": 3,
            "minimum_bid_increment": "100",
        },
    ).json()

    create_bid(client, first, auction["id"], amount="1100")
    create_bid(client, second, auction["id"], amount="1300")

    note = db_session.scalar(
        select(Notification).where(
            Notification.user_id == first.id, Notification.type == NotificationType.OUTBID
        )
    )
    assert note is not None
    assert "Nikon Z50 kamera" in (note.body or "")
    assert "Joriy narx: 13 soʻm" in (note.body or "")  # 1 300 tiyin = 13 so'm, ".00" yo'q
    assert [chat for chat, _ in recorder.sent] == ["chat-first"]
    assert f"https://bazart.uz/lot/{auction['id']}" in recorder.sent[0][1]


# --- "2 soat qoldi" ---------------------------------------------------------------


def test_ending_soon_fires_two_hours_before_end(client: TestClient, db_session: Session) -> None:
    assert settings.ending_soon_lead_minutes == 120
    seller = create_user(client, db_session, email="seller@example.com")
    watcher = create_user(client, db_session, email="watcher@example.com")
    item = create_item(client, seller, starting_price="1000")
    now = datetime.now(UTC)
    auction = client.post(
        "/api/v1/auctions",
        headers=seller.headers,
        json={
            "item_id": item["id"],
            "start_time": (now - timedelta(minutes=1)).isoformat(),
            "end_time": (now + timedelta(minutes=110)).isoformat(),
        },
    ).json()
    client.post("/api/v1/watchlist", headers=watcher.headers, json={"auction_id": auction["id"]})

    assert notify_ending_soon(db_session) == 1
    note = db_session.scalar(
        select(Notification).where(Notification.type == NotificationType.ENDING_SOON)
    )
    assert note is not None
    assert note.user_id == watcher.id
    assert note.title == "Tugashiga 2 soat qoldi"


def test_format_soum_text_drops_only_zero_fraction() -> None:
    from app.money import format_soum_text

    assert format_soum_text(420_000_000) == "4 200 000"
    assert format_soum_text(6_200_050) == "62 000.50"  # tiyin saqlanadi, yaxlitlanmaydi
    assert format_soum_text(0) == "0"
