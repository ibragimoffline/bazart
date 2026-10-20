"""Auksion WebSocket JWT auth testlari.

WS endpoint ochiq emas: ulangandan keyin birinchi xabar `{"type": "AUTH", "token": ...}`
bo'lishi SHART (token URL'da — log'larga tushmasin). Eski `?token=` vaqtincha qabul
qilinadi. Token yo'q yoki yaroqsiz bo'lsa server 4401 kod bilan yopadi — TestClient
buni `WebSocketDisconnect` sifatida ko'taradi.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.api.v1.endpoints import ws as ws_endpoint
from app.api.v1.endpoints.ws import WS_UNAUTHORIZED_CODE
from tests.conftest import create_user


def test_connection_without_auth_message_times_out(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUTH xabari kelmasa ulanish kutish muddatidan keyin 4401 bilan yopiladi."""
    monkeypatch.setattr(ws_endpoint, "WS_AUTH_TIMEOUT_SECONDS", 0.2)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/auctions/1") as ws:
            # accept'dan keyin close bo'lgani uchun uzilish birinchi receive'da chiqadi.
            ws.receive_json()

    assert exc_info.value.code == WS_UNAUTHORIZED_CODE


def test_first_message_must_be_auth(client: TestClient, db_session: Session) -> None:
    """Birinchi xabar AUTH bo'lmasa (masalan relay xabari) — room'ga qo'shilmaydi."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/auctions/1") as ws:
            ws.send_json({"type": "PING"})
            ws.receive_json()

    assert exc_info.value.code == WS_UNAUTHORIZED_CODE


def test_auth_message_with_invalid_token_is_rejected(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/auctions/1") as ws:
            ws.send_json({"type": "AUTH", "token": "not-a-real-jwt"})
            ws.receive_json()

    assert exc_info.value.code == WS_UNAUTHORIZED_CODE


def test_auth_message_with_valid_token_succeeds(client: TestClient, db_session: Session) -> None:
    """Token URL'da emas, birinchi xabarda — AUTH_OK, keyin relay ishlaydi."""
    tok = create_user(client, db_session, email="wsauth-msg@example.com").access_token

    with client.websocket_connect("/api/v1/ws/auctions/1") as ws:
        ws.send_json({"type": "AUTH", "token": tok})
        assert ws.receive_json() == {"type": "AUTH_OK"}
        ws.send_json({"type": "PING"})
        assert ws.receive_json() == {"type": "PING"}


def test_connection_with_invalid_token_is_rejected(client: TestClient) -> None:
    """Eski yo'l: yaroqsiz (soxta) `?token=` bilan ulanish rad etiladi."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/v1/ws/auctions/1?token=not-a-real-jwt") as ws:
            ws.receive_json()

    assert exc_info.value.code == WS_UNAUTHORIZED_CODE


def test_connection_with_valid_token_succeeds(client: TestClient, db_session: Session) -> None:
    """Eski yo'l (`?token=`, vaqtincha): to'g'ri access token bilan relay ishlaydi."""
    tok = create_user(client, db_session, email="wsauth@example.com").access_token

    with client.websocket_connect(f"/api/v1/ws/auctions/1?token={tok}") as ws:
        payload = {"type": "PING"}
        ws.send_json(payload)
        # broadcast room'dagi BARCHA ulanishlarga (jumladan yuboruvchiga)
        # yuboradi — echo qaytishi ulanish to'liq ochiq va relay ishlashini
        # tasdiqlaydi (4401 bilan yopilmagan).
        assert ws.receive_json() == payload
