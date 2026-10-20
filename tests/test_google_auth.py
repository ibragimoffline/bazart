"""Google orqali kirish: ID token tekshiruvi va akkaunt bog'lash qoidalari.

Google JWKS o'rniga test RSA kaliti ishlatiladi, lekin `jwt.decode` haqiqiy —
imzo, `aud`, `iss` va muddat tekshiruvi aynan prod'dagidek ishlaydi.
"""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.repositories.user_repository import UserRepository
from app.services import google_identity
from tests.conftest import TEST_PASSWORD, login_user, register_user

CLIENT_ID = "test-client.apps.googleusercontent.com"
GOOGLE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
URL = "/api/v1/auth/google"


@pytest.fixture(autouse=True)
def google_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    fake_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=GOOGLE_KEY.public_key())
    )
    monkeypatch.setattr(google_identity, "_jwks_client", lambda: fake_client)


def make_credential(key: rsa.RSAPrivateKey = GOOGLE_KEY, **overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "google-sub-1",
        "email": "aziza@gmail.com",
        "email_verified": True,
        "name": "Aziza Karimova",
        "picture": "https://lh3.googleusercontent.com/a/photo",
        "iat": now,
        "exp": now + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


def test_google_creates_new_verified_user(client: TestClient) -> None:
    response = client.post(URL, json={"credential": make_credential()})
    assert response.status_code == 200

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    ).json()
    assert me["email"] == "aziza@gmail.com"
    assert me["full_name"] == "Aziza Karimova"
    assert me["is_verified"] is True


def test_google_second_login_returns_same_user(client: TestClient, db_session: Session) -> None:
    client.post(URL, json={"credential": make_credential()})
    # Email Google tomonida o'zgargan — baribir `sub` bo'yicha o'sha akkaunt.
    response = client.post(URL, json={"credential": make_credential(email="new@gmail.com")})
    assert response.status_code == 200
    user = UserRepository(db_session).get_by_google_sub("google-sub-1")
    assert user is not None
    assert user.email == "aziza@gmail.com"


def test_google_links_existing_verified_account_and_keeps_password(
    client: TestClient, db_session: Session
) -> None:
    register_user(client, email="aziza@gmail.com")
    user = UserRepository(db_session).get_by_email("aziza@gmail.com")
    assert user is not None
    UserRepository(db_session).mark_verified(user)

    assert client.post(URL, json={"credential": make_credential()}).status_code == 200
    db_session.refresh(user)
    assert user.google_sub == "google-sub-1"
    login_user(client, email="aziza@gmail.com")


def test_google_link_resets_password_of_unverified_account(
    client: TestClient, db_session: Session
) -> None:
    """Begona odam emailni oldindan band qilgan bo'lsa, uning paroli bekor bo'ladi."""
    register_user(client, email="aziza@gmail.com")

    assert client.post(URL, json={"credential": make_credential()}).status_code == 200
    user = UserRepository(db_session).get_by_email("aziza@gmail.com")
    assert user is not None
    db_session.refresh(user)
    assert user.is_verified is True
    assert not verify_password(TEST_PASSWORD, user.hashed_password)


def test_google_unverified_email_is_not_linked(client: TestClient, db_session: Session) -> None:
    register_user(client, email="aziza@gmail.com")
    response = client.post(URL, json={"credential": make_credential(email_verified=False)})
    assert response.status_code == 401
    assert UserRepository(db_session).get_by_google_sub("google-sub-1") is None


@pytest.mark.parametrize(
    "credential",
    [
        pytest.param(lambda: make_credential(aud="other-app"), id="wrong-audience"),
        pytest.param(lambda: make_credential(iss="https://evil.example"), id="wrong-issuer"),
        pytest.param(lambda: make_credential(exp=int(time.time()) - 10), id="expired"),
        pytest.param(
            lambda: make_credential(
                key=rsa.generate_private_key(public_exponent=65537, key_size=2048)
            ),
            id="forged-signature",
        ),
        pytest.param(lambda: "not-a-jwt", id="garbage"),
    ],
)
def test_google_rejects_invalid_credentials(client: TestClient, credential) -> None:
    response = client.post(URL, json={"credential": credential()})
    assert response.status_code == 401


def test_google_disabled_without_client_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "google_client_id", "")
    response = client.post(URL, json={"credential": make_credential()})
    assert response.status_code == 503


def test_google_login_gets_same_refresh_session(client: TestClient) -> None:
    """Google kirishdan keyin Bazart sessiyasi — access eskirsa Google qayta so'ralmaydi."""
    response = client.post(URL, json={"credential": make_credential()})
    assert response.status_code == 200
    assert "refresh_token" not in response.json()
    refresh_cookie = response.cookies[settings.refresh_cookie_name]

    client.cookies.clear()
    refreshed = client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{settings.refresh_cookie_name}={refresh_cookie}"},
    )
    assert refreshed.status_code == 200
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "aziza@gmail.com"
