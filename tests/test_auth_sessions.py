"""Refresh-sessiyalar: HttpOnly cookie, rotation, replay detection, logout.

Foydalanuvchi 30 daqiqalik access token eskirgani uchun chiqib ketmasligi kerak, lekin
o'g'irlangan refresh token qayta ishlatilsa sessiya yopilishi kerak. Vaqt kutilmaydi:
eskirgan tokenlar to'g'ridan-to'g'ri yasaladi, sessiya vaqtlari bazada suriladi.
"""

import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_session_refresh_token,
    create_token,
)
from app.models.auth_session import AuthSession
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from tests.conftest import (
    AuthenticatedUser,
    auth_headers,
    create_auction,
    create_item,
    create_user,
)

REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
COOKIE = settings.refresh_cookie_name


def _claims(token: str) -> dict:
    return jwt.decode(token, options={"verify_signature": False})


def _session(db: Session, token: str) -> AuthSession:
    db.expire_all()
    session = db.get(AuthSession, uuid.UUID(_claims(token)["sid"]))
    assert session is not None
    return session


def _post(client: TestClient, url: str, token: str | None = None, **headers: str):
    """Brauzer kabi: refresh token faqat cookie'da. Jar tozalanadi — testlar aralashmasin."""
    client.cookies.clear()
    if token is not None:
        headers["Cookie"] = f"{COOKIE}={token}"
    return client.post(url, headers=headers)


def _expired_access(user_id: int) -> str:
    return create_token(str(user_id), ACCESS_TOKEN_TYPE, timedelta(seconds=-1))


def _cleared_cookie(response) -> bool:
    return any(
        h.startswith(f"{COOKIE}=") and "Max-Age=0" in h
        for h in response.headers.get_list("set-cookie")
    )


@pytest.fixture
def user(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="session@example.com")


def test_login_sets_httponly_cookie_not_body(client: TestClient, user: AuthenticatedUser) -> None:
    response = client.post(
        "/api/v1/auth/login", data={"username": user.email, "password": user.password}
    )
    assert response.status_code == 200
    body = response.json()
    assert "refresh_token" not in body
    assert body["expires_in"] == settings.access_token_expire_minutes * 60

    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{COOKIE}="))
    assert "HttpOnly" in header
    assert f"Path={settings.refresh_cookie_path}" in header
    assert "SameSite=lax" in header


def test_expired_access_is_restored_via_refresh(
    client: TestClient, user: AuthenticatedUser
) -> None:
    """Asosiy xato: access eskirgach sessiya tiklanishi kerak, chiqarib yuborilmasligi."""
    assert client.get(ME, headers=auth_headers(_expired_access(user.id))).status_code == 401

    refreshed = _post(client, REFRESH, user.refresh_token)
    assert refreshed.status_code == 200
    me = client.get(ME, headers=auth_headers(refreshed.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == user.email


def test_refresh_rotates_and_extends_session(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    before = _session(db_session, user.refresh_token)
    old_expiry = before.expires_at

    response = _post(client, REFRESH, user.refresh_token)
    assert response.status_code == 200
    new_token = response.cookies[COOKIE]
    assert new_token != user.refresh_token
    assert _claims(new_token)["sid"] == _claims(user.refresh_token)["sid"]

    after = _session(db_session, new_token)
    assert after.current_jti == _claims(new_token)["jti"]
    assert after.previous_jti == _claims(user.refresh_token)["jti"]
    assert after.expires_at >= old_expiry

    # Yangi token navbatdagi refresh'da ham ishlaydi (zanjir uzilmaydi).
    assert _post(client, REFRESH, new_token).status_code == 200


def test_concurrent_refresh_with_same_token_keeps_session(
    client: TestClient,
    db_session: Session,
    db_engine: Engine,
    user: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ikki tab bir vaqtda bitta cookie bilan: ikkalasi ham ishlaydi, sessiya bekor bo'lmaydi.

    Har oqim sessiya qatorini o'qigach to'xtab, ikkinchisini kutadi. Qulf (FOR UPDATE) bor
    bo'lsa ikkinchi oqim qatorni birinchisi commit qilmaguncha o'qiy olmaydi (kutish
    timeout bilan tugaydi) va grace yo'liga tushadi. Qulf olib tashlansa ikkalasi bir xil
    eski jti'ni ko'rib turli yangi jti yozadi — biri yo'qoladi va test yiqiladi.
    """
    factory = sessionmaker(bind=db_engine, autoflush=False)
    start = threading.Barrier(2)
    loaded = threading.Barrier(2, timeout=1.5)
    original = AuthSessionRepository.get_for_update

    def paused_get_for_update(self: AuthSessionRepository, session_id: uuid.UUID):
        row = original(self, session_id)
        try:
            loaded.wait()
        except threading.BrokenBarrierError:
            pass
        return row

    monkeypatch.setattr(AuthSessionRepository, "get_for_update", paused_get_for_update)
    results: list[str] = []
    errors: list[BaseException] = []

    def worker() -> None:
        with factory() as db:
            try:
                start.wait()
                results.append(AuthService(db).refresh_session(user.refresh_token).refresh_token)
            except BaseException as exc:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    session = _session(db_session, user.refresh_token)
    assert session.revoked_at is None
    assert {_claims(token)["jti"] for token in results} == {session.current_jti}
    assert _post(client, REFRESH, results[0]).status_code == 200


def test_previous_token_within_grace_is_not_replay(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    first = _post(client, REFRESH, user.refresh_token)
    assert first.status_code == 200

    # Ikkinchi tab hali eski cookie bilan (javob kelguncha) — grace oynasida.
    second = _post(client, REFRESH, user.refresh_token)
    assert second.status_code == 200
    assert _claims(second.cookies[COOKIE])["jti"] == _claims(first.cookies[COOKIE])["jti"]
    assert _session(db_session, user.refresh_token).revoked_at is None


def test_replay_outside_grace_revokes_whole_session(
    client: TestClient,
    db_session: Session,
    user: AuthenticatedUser,
    caplog: pytest.LogCaptureFixture,
) -> None:
    rotated = _post(client, REFRESH, user.refresh_token)
    assert rotated.status_code == 200
    current = rotated.cookies[COOKIE]

    session = _session(db_session, current)
    session.rotated_at = datetime.now(UTC) - timedelta(
        seconds=settings.refresh_reuse_grace_seconds + 1
    )
    db_session.commit()

    with caplog.at_level(logging.WARNING):
        replay = _post(client, REFRESH, user.refresh_token)
    assert replay.status_code == 401
    assert _cleared_cookie(replay)
    assert _session(db_session, current).revoke_reason == "reuse"
    # Hujumchi ham, qonuniy egasi ham endi refresh qila olmaydi — qayta kirish kerak.
    assert _post(client, REFRESH, current).status_code == 401
    # Log'da token qiymati yo'q.
    assert "qayta ishlatildi" in caplog.text
    assert user.refresh_token not in caplog.text
    assert current not in caplog.text


def test_token_two_rotations_old_is_replay(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    second = _post(client, REFRESH, user.refresh_token).cookies[COOKIE]
    third = _post(client, REFRESH, second).cookies[COOKIE]
    assert _post(client, REFRESH, user.refresh_token).status_code == 401
    assert _session(db_session, third).revoke_reason == "reuse"


def test_expired_session_requires_login(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    session = _session(db_session, user.refresh_token)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    response = _post(client, REFRESH, user.refresh_token)
    assert response.status_code == 401
    assert _cleared_cookie(response)


def test_expired_refresh_jwt_requires_login(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    session = _session(db_session, user.refresh_token)
    expired = create_session_refresh_token(
        str(user.id), str(session.id), session.current_jti, datetime.now(UTC) - timedelta(1)
    )
    assert _post(client, REFRESH, expired).status_code == 401


def test_refresh_without_cookie_is_401(client: TestClient) -> None:
    assert _post(client, REFRESH).status_code == 401


def test_inactive_user_cannot_refresh(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    account = UserRepository(db_session).get_by_id(user.id)
    assert account is not None
    account.is_active = False
    db_session.commit()
    assert _post(client, REFRESH, user.refresh_token).status_code == 401


def test_logout_with_expired_access_still_revokes_session(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    client.cookies.clear()
    response = client.post(
        LOGOUT,
        headers={
            **auth_headers(_expired_access(user.id)),
            "Cookie": f"{COOKIE}={user.refresh_token}",
        },
    )
    assert response.status_code == 200
    assert _cleared_cookie(response)
    assert _session(db_session, user.refresh_token).revoke_reason == "logout"
    assert _post(client, REFRESH, user.refresh_token).status_code == 401


def test_logout_revokes_access_token(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    client.cookies.clear()
    response = client.post(
        LOGOUT, headers={**user.headers, "Cookie": f"{COOKIE}={user.refresh_token}"}
    )
    assert response.status_code == 200
    assert client.get(ME, headers=user.headers).status_code == 401


def test_logout_without_any_token_is_ok(client: TestClient) -> None:
    response = _post(client, LOGOUT)
    assert response.status_code == 200
    assert _cleared_cookie(response)


def test_untrusted_origin_is_rejected(client: TestClient, user: AuthenticatedUser) -> None:
    evil = _post(client, REFRESH, user.refresh_token, Origin="https://evil.example")
    assert evil.status_code == 403
    assert (
        _post(client, LOGOUT, user.refresh_token, Origin="https://evil.example").status_code == 403
    )

    trusted = _post(client, REFRESH, user.refresh_token, Origin=settings.cors_origins[0])
    assert trusted.status_code == 200


def test_legacy_body_token_migrates_once(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    """Eski klient: refresh token localStorage'da (sid'siz). Bir marta cookie'ga o'tadi."""
    legacy = create_token(
        str(user.id), REFRESH_TOKEN_TYPE, timedelta(days=settings.refresh_token_expire_days)
    )
    client.cookies.clear()
    migrated = client.post(REFRESH, json={"refresh_token": legacy})
    assert migrated.status_code == 200
    cookie = migrated.cookies[COOKIE]
    assert _session(db_session, cookie).revoked_at is None

    client.cookies.clear()
    assert client.post(REFRESH, json={"refresh_token": legacy}).status_code == 401
    assert _post(client, REFRESH, cookie).status_code == 200


def test_password_reset_revokes_sessions(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    reset = client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    token = reset.json()["reset_token"]
    assert (
        client.post(
            "/api/v1/auth/reset-password", json={"token": token, "new_password": "Password2"}
        ).status_code
        == 200
    )
    assert _session(db_session, user.refresh_token).revoke_reason == "password_reset"
    assert _post(client, REFRESH, user.refresh_token).status_code == 401


def test_marketplace_actions_work_after_renewal(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    """Yangilangan access token bilan bid va taklif odatdagidek ishlaydi."""
    seller = create_user(client, db_session, email="seller-session@example.com")
    auction = create_auction(client, seller, create_item(client, seller)["id"])

    access = _post(client, REFRESH, user.refresh_token).json()["access_token"]
    headers = auth_headers(access)

    bid = client.post(f"/api/v1/bids/{auction['id']}", headers=headers, json={"amount": "1100"})
    assert bid.status_code == 201, bid.text

    listing = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={"title": "Xiaomi Redmi Note 13", "condition": "new", "starting_price": "300000"},
    ).json()
    published = client.post(
        f"/api/v1/items/{listing['id']}/publish", headers=seller.headers, json={"duration_days": 5}
    )
    assert published.status_code == 200, published.text
    offer = client.post(
        f"/api/v1/items/{listing['id']}/offers",
        headers=headers,
        json={"quantity": 1, "unit_price": "250000"},
    )
    assert offer.status_code == 201, offer.text


def test_grace_reissue_does_not_extend_session(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    """Grace yo'li sessiyani uzaytirmaydi — replay qiluvchi muddatni sura olmaydi."""
    assert _post(client, REFRESH, user.refresh_token).status_code == 200
    expiry = _session(db_session, user.refresh_token).expires_at

    again = _post(client, REFRESH, user.refresh_token)
    assert again.status_code == 200
    assert _session(db_session, user.refresh_token).expires_at == expiry
    assert datetime.fromtimestamp(_claims(again.cookies[COOKIE])["exp"], UTC) <= expiry


def test_stolen_token_used_first_is_detected_when_owner_returns(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    """Hujumchi o'g'irlangan tokenni egasidan oldin ishlatadi va yangilab turadi.

    Egasi qaytib (grace'dan keyin) eski cookie bilan kelganda sessiya bekor bo'ladi —
    hujumchining yangi tokenlari ham ishlamay qoladi.
    """
    attacker = _post(client, REFRESH, user.refresh_token).cookies[COOKIE]
    attacker = _post(client, REFRESH, attacker).cookies[COOKIE]

    session = _session(db_session, attacker)
    session.rotated_at = datetime.now(UTC) - timedelta(
        seconds=settings.refresh_reuse_grace_seconds + 1
    )
    db_session.commit()

    assert _post(client, REFRESH, user.refresh_token).status_code == 401
    assert _post(client, REFRESH, attacker).status_code == 401
    assert _session(db_session, attacker).revoke_reason == "reuse"


def test_rotation_never_passes_absolute_lifetime(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    session = _session(db_session, user.refresh_token)
    session.created_at = datetime.now(UTC) - timedelta(days=settings.refresh_session_max_days - 1)
    db_session.commit()
    absolute_end = session.created_at + timedelta(days=settings.refresh_session_max_days)

    response = _post(client, REFRESH, user.refresh_token)
    assert response.status_code == 200
    assert _session(db_session, user.refresh_token).expires_at == absolute_end
    cookie_exp = _claims(response.cookies[COOKIE])["exp"]
    assert cookie_exp <= int(absolute_end.timestamp())


def test_session_ends_at_absolute_lifetime_even_if_active(
    client: TestClient, db_session: Session, user: AuthenticatedUser
) -> None:
    session = _session(db_session, user.refresh_token)
    session.created_at = datetime.now(UTC) - timedelta(
        days=settings.refresh_session_max_days, seconds=1
    )
    db_session.commit()

    response = _post(client, REFRESH, user.refresh_token)
    assert response.status_code == 401
    assert _cleared_cookie(response)


def test_settings_reject_max_lifetime_shorter_than_sliding() -> None:
    with pytest.raises(ValueError, match="REFRESH_SESSION_MAX_DAYS"):
        settings.__class__(refresh_token_expire_days=14, refresh_session_max_days=7)


def _prod_settings(**overrides):
    return settings.__class__(
        environment="production",
        secret_key="p" * 48,
        psp_webhook_secret="w" * 48,
        sms_provider="eskiz",
        eskiz_email="sms@example.uz",
        eskiz_password="x",
        **overrides,
    )


def test_production_forces_secure_cookie() -> None:
    assert _prod_settings().refresh_cookie_secure_effective is True
    with pytest.raises(ValueError, match="REFRESH_COOKIE_SECURE"):
        _prod_settings(refresh_cookie_secure=False)


def test_samesite_none_requires_secure() -> None:
    with pytest.raises(ValueError, match="SameSite=None"):
        settings.__class__(refresh_cookie_samesite="none", refresh_cookie_secure=False)


def test_production_cookie_header_is_secure(
    client: TestClient, user: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    response = _post(client, REFRESH, user.refresh_token)
    assert response.status_code == 200
    header = next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{COOKIE}="))
    assert "Secure" in header and "HttpOnly" in header and "SameSite=lax" in header
