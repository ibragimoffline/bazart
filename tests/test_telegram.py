"""Telegram bildirishnoma kanali testlari.

Qamrov:
- provayder tanlovi (`get_telegram_provider`) — token/enabled holatiga qarab
  Log yoki Http;
- `HttpTelegramProvider` best-effort: tarmoq/HTTP xatosi istisno emas, False;
- `notification_service.create()` -> Telegram ulanishi (chat_id bo'lsa yetkazadi,
  bo'lmasa yo'q) — mavjud OUTBID/WON oqimini buzmasdan;
- endpointlar: chat ulash va til yangilash (faqat egaga).

Bu fayl testlarni YOZADI, ishga tushirmaydi.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import NotificationType
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.telegram_provider import (
    HttpTelegramProvider,
    LogTelegramProvider,
    get_telegram_provider,
)
from app.tasks import notifications as notifications_task
from tests.conftest import create_user

# --- Provayder tanlovi -------------------------------------------------------


def test_get_provider_returns_log_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """telegram_enabled=False -> Log provayder (graceful fallback)."""
    monkeypatch.setattr(settings, "telegram_enabled", False)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert isinstance(get_telegram_provider(), LogTelegramProvider)


def test_get_provider_returns_log_when_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Yoqilgan, lekin token bo'sh -> baribir Log (ilova yiqilmasin)."""
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert isinstance(get_telegram_provider(), LogTelegramProvider)


def test_get_provider_returns_http_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Yoqilgan va token bor -> real HTTP provayder."""
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "12345:abc")
    assert isinstance(get_telegram_provider(), HttpTelegramProvider)


# --- LogTelegramProvider -----------------------------------------------------


def test_log_provider_send_returns_true() -> None:
    assert LogTelegramProvider().send_message("42", "salom") is True


# --- HttpTelegramProvider best-effort ---------------------------------------


def test_http_provider_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/bot12345:abc/sendMessage"
        return httpx.Response(200, json={"ok": True})

    provider = HttpTelegramProvider(
        token="12345:abc", timeout=5.0, transport=httpx.MockTransport(handler)
    )
    assert provider.send_message("42", "salom") is True


def test_http_provider_swallows_http_error() -> None:
    """4xx/5xx istisno ko'tarmaydi — best-effort, False qaytaradi."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    provider = HttpTelegramProvider(token="t", timeout=5.0, transport=httpx.MockTransport(handler))
    assert provider.send_message("42", "salom") is False


def test_http_provider_swallows_network_error() -> None:
    """Tarmoq xatosi ham yutiladi — oqim bloklanmaydi."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("tarmoq yo'q")

    provider = HttpTelegramProvider(token="t", timeout=5.0, transport=httpx.MockTransport(handler))
    assert provider.send_message("42", "salom") is False


# --- notification_service -> Telegram ulanishi -------------------------------


class _RecordingProvider:
    """Testda yetkazilgan xabarlarni yig'uvchi soxta provayder."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_message(self, chat_id: str, text: str) -> bool:
        self.sent.append((chat_id, text))
        return True


def test_notification_delivers_to_telegram_when_chat_id_set(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chat_id ulangan bo'lsa — notification Telegram'ga ham yetadi (best-effort)."""
    recorder = _RecordingProvider()
    monkeypatch.setattr(notifications_task, "get_telegram_provider", lambda: recorder)

    user = create_user(client, db_session, email="tg@example.com")
    db_user = db_session.get(User, user.id)
    assert db_user is not None
    db_user.telegram_chat_id = "chat-999"
    db_session.commit()

    NotificationService(db_session).create(
        user_id=user.id,
        type=NotificationType.OUTBID,
        title="Sizni ortda qoldirishdi",
        body="Yangi taklif qo'ying.",
    )
    # Tashqi yetkazish faqat COMMIT'dan keyin (rollback bo'lsa umuman ketmaydi).
    assert recorder.sent == []
    db_session.commit()

    assert recorder.sent == [("chat-999", "Sizni ortda qoldirishdi\n\nYangi taklif qo'ying.")]


def test_notification_skips_telegram_without_chat_id(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """chat_id yo'q -> Telegram chaqirilmaydi, in-app oqim buzilmaydi."""
    recorder = _RecordingProvider()
    monkeypatch.setattr(notifications_task, "get_telegram_provider", lambda: recorder)

    user = create_user(client, db_session, email="notg@example.com")
    NotificationService(db_session).create(
        user_id=user.id,
        type=NotificationType.WON,
        title="Yutdingiz",
    )
    db_session.commit()

    assert recorder.sent == []


# --- Endpointlar -------------------------------------------------------------


def test_link_telegram_endpoint(client: TestClient, db_session: Session) -> None:
    user = create_user(client, db_session, email="link@example.com")

    response = client.post(
        "/api/v1/users/me/telegram",
        headers=user.headers,
        json={"chat_id": "555"},
    )
    assert response.status_code == 200
    assert response.json()["telegram_chat_id"] == "555"

    # GET /me egaga chat_id ni ko'rsatadi.
    me = client.get("/api/v1/users/me", headers=user.headers)
    assert me.json()["telegram_chat_id"] == "555"


def test_update_preferences_endpoint(client: TestClient, db_session: Session) -> None:
    user = create_user(client, db_session, email="lang@example.com")

    response = client.patch(
        "/api/v1/users/me/preferences",
        headers=user.headers,
        json={"preferred_language": "ru"},
    )
    assert response.status_code == 200
    assert response.json()["preferred_language"] == "ru"


def test_update_preferences_rejects_unknown_language(
    client: TestClient, db_session: Session
) -> None:
    user = create_user(client, db_session, email="badlang@example.com")
    response = client.patch(
        "/api/v1/users/me/preferences",
        headers=user.headers,
        json={"preferred_language": "en"},
    )
    assert response.status_code == 422


def test_link_telegram_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/users/me/telegram", json={"chat_id": "1"})
    assert response.status_code == 401


def test_rolled_back_notification_is_never_delivered(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tranzaksiya bekor bo'lsa — DB'da ham, Telegram'da ham xabar yo'q."""
    recorder = _RecordingProvider()
    monkeypatch.setattr(notifications_task, "get_telegram_provider", lambda: recorder)
    user = create_user(client, db_session, email="rb@example.com")
    db_user = db_session.get(User, user.id)
    db_user.telegram_chat_id = "chat-1"
    db_session.commit()

    NotificationService(db_session).create(
        user_id=user.id, type=NotificationType.OUTBID, title="Yuborilmasligi kerak"
    )
    db_session.rollback()
    db_session.commit()

    assert recorder.sent == []
    assert client.get("/api/v1/notifications", headers=user.headers).json() == []
