"""Telefon OTP: tasdiqlash, almashtirish, suiiste'moldan himoya, SMS provayderlari (docs/AUTH.md).

Testlar "test" muhitida: `debug_code` javobda qaytadi (log provayderi), shuning uchun kod SMS
log'idan qidirilmaydi. Prod cheklovlari settings'ni o'zgartirib alohida sinaladi.
"""

import logging
import re
import threading
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import ACCESS_TOKEN_TYPE, create_access_token, create_token
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.otp import OtpCode
from app.models.user import User
from app.repositories.otp_repository import OtpRepository
from app.schemas.user import normalize_phone
from app.services import otp_service as otp_module
from app.services.otp_service import (
    PHONE_TAKEN,
    REAUTH_REQUIRED,
    SMS_SEND_FAILED,
    OtpService,
    _hash_code,
)
from app.services.sms_provider import (
    EskizSmsProvider,
    LogSmsProvider,
    NullSmsProvider,
    SmsDeliveryError,
    SmsResult,
    available_provider_names,
    get_sms_provider,
)
from tests.conftest import TEST_PASSWORD, AuthenticatedUser, auth_headers, create_user
from tests.test_google_auth import google_configured, make_credential  # noqa: F401

PHONE = "+998901112233"
OTHER = "+998935557788"
REQUEST = "/api/v1/auth/otp/request"
VERIFY = "/api/v1/auth/otp/verify"

# Telefon tasdig'i sinovlari tasdiqlanmagan foydalanuvchidan boshlanadi.
pytestmark = pytest.mark.usefixtures("unverified_phones")


@pytest.fixture
def me(client: TestClient, db_session: Session) -> AuthenticatedUser:
    return create_user(client, db_session, email="dilnoza@example.com")


@pytest.fixture
def no_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "otp_resend_cooldown_seconds", 0)


def _request(client: TestClient, user: AuthenticatedUser, phone: str = PHONE, **extra):
    return client.post(REQUEST, headers=user.headers, json={"phone": phone, **extra})


def _code(client: TestClient, user: AuthenticatedUser, phone: str = PHONE, **extra) -> str:
    response = _request(client, user, phone, **extra)
    assert response.status_code == 200, response.text
    return response.json()["debug_code"]


def _verify(client: TestClient, user: AuthenticatedUser, code: str, phone: str = PHONE):
    return client.post(VERIFY, headers=user.headers, json={"phone": phone, "code": code})


def _user(db: Session, user_id: int) -> User:
    db.expire_all()
    return db.get(User, user_id)


def _verified(db: Session, user: AuthenticatedUser, phone: str) -> None:
    row = _user(db, user.id)
    row.phone = phone
    row.phone_verified_at = datetime.now(UTC)
    db.commit()


def _stale_headers(user: AuthenticatedUser) -> dict[str, str]:
    """Access token, login 1 soat oldin bo'lgan (qayta autentifikatsiya oynasidan tashqari)."""
    old = datetime.now(UTC) - timedelta(hours=1)
    return auth_headers(create_access_token(str(user.id), auth_time=old))


# --- 1-2. Raqam formati -----------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    ["+998901112233", "998901112233", "+998 90 111-22-33", "(90) 111 22 33", "00998901112233"],
)
def test_uz_phone_formats_normalize_to_e164(raw: str) -> None:
    assert normalize_phone(raw) == PHONE


@pytest.mark.parametrize("raw", ["+1 555 010 0100", "12345", "+99890111223", "9989011122334", "x"])
def test_invalid_phone_rejected(client: TestClient, me: AuthenticatedUser, raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)
    assert _request(client, me, raw).status_code == 422


def test_request_and_verify_require_login(client: TestClient) -> None:
    assert client.post(REQUEST, json={"phone": PHONE}).status_code == 401
    assert client.post(VERIFY, json={"phone": PHONE, "code": "123456"}).status_code == 401


def test_other_purposes_are_not_supported(client: TestClient, me: AuthenticatedUser) -> None:
    for purpose in ("login", "password_reset"):
        assert _request(client, me, purpose=purpose).status_code == 400


# --- 3. Muvaffaqiyatli tasdiq + sessiya (14) ----------------------------------------


def test_successful_verification_sets_phone_and_keeps_session(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    response = _request(client, me, "90 111 22 33")
    assert response.status_code == 200
    body = response.json()
    assert len(body["debug_code"]) == 6 and body["debug_code"].isdigit()
    assert body["resend_after_seconds"] == settings.otp_resend_cooldown_seconds
    assert datetime.fromisoformat(body["expires_at"]) - datetime.now(UTC) <= timedelta(minutes=5)

    verified = _verify(client, me, body["debug_code"])
    assert verified.status_code == 200
    assert verified.json()["phone_verified"] is True
    user = _user(db_session, me.id)
    assert user.phone == PHONE and user.phone_verified_at is not None

    # Sessiya buzilmaydi: access token ham, refresh cookie ham ishlaydi.
    assert client.get("/api/v1/auth/me", headers=me.headers).status_code == 200
    client.cookies.clear()
    refreshed = client.post(
        "/api/v1/auth/refresh",
        headers={"Cookie": f"{settings.refresh_cookie_name}={me.refresh_token}"},
    )
    assert refreshed.status_code == 200


def test_code_is_hashed_not_plaintext(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    code = _code(client, me)
    stored = db_session.scalar(select(OtpCode).where(OtpCode.user_id == me.id))
    assert stored.code_hash == _hash_code(code)
    assert code not in stored.code_hash


# --- 4-6. Noto'g'ri, eskirgan, urinishlar ---------------------------------------------


def test_wrong_code_counts_attempt(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    code = _code(client, me)
    wrong = "000000" if code != "000000" else "111111"
    assert _verify(client, me, wrong).status_code == 400
    assert db_session.scalar(select(OtpCode.attempts).where(OtpCode.user_id == me.id)) == 1
    assert _user(db_session, me.id).phone_verified_at is None


def test_expired_code_rejected(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    code = _code(client, me)
    otp = db_session.scalar(select(OtpCode).where(OtpCode.user_id == me.id))
    otp.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert _verify(client, me, code).status_code == 400


def test_max_attempts_locks_challenge(
    client: TestClient, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "otp_max_attempts", 3)
    code = _code(client, me)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(3):
        assert _verify(client, me, wrong).status_code == 400
    # Endi to'g'ri kod ham qabul qilinmaydi — yangisini so'rash kerak.
    assert _verify(client, me, code).status_code == 429


# --- 7-8. Cooldown va limitlar ---------------------------------------------------------


def test_resend_cooldown_per_phone_and_per_account(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    _code(client, me)
    again = _request(client, me)
    assert again.status_code == 429
    assert int(again.headers["Retry-After"]) <= settings.otp_resend_cooldown_seconds
    # Boshqa raqamga o'tib ham cooldown chetlab o'tilmaydi (akkaunt bo'yicha).
    assert _request(client, me, OTHER).status_code == 429
    # Boshqa akkaunt shu raqamga ham kutadi (SMS bombing).
    other = create_user(client, db_session, email="other@example.com")
    assert _request(client, other).status_code == 429


@pytest.mark.usefixtures("no_cooldown")
def test_daily_limits_per_phone_account_and_ip(
    client: TestClient, db_session: Session, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "otp_daily_limit_per_phone", 2)
    _code(client, me)
    _code(client, me)
    assert _request(client, me).status_code == 429  # raqam limiti

    monkeypatch.setattr(settings, "otp_daily_limit_per_phone", 100)
    monkeypatch.setattr(settings, "otp_daily_limit_per_user", 3)
    _code(client, me, OTHER)
    assert _request(client, me, "+998941234567").status_code == 429  # akkaunt limiti

    monkeypatch.setattr(settings, "otp_daily_limit_per_user", 100)
    monkeypatch.setattr(settings, "otp_daily_limit_per_ip", 3)
    second = create_user(client, db_session, email="second@example.com")
    assert _request(client, second, "+998971234567").status_code == 429  # IP limiti


@pytest.mark.usefixtures("no_cooldown")
def test_new_code_invalidates_previous(client: TestClient, me: AuthenticatedUser) -> None:
    first = _code(client, me)
    second = _code(client, me)
    if first != second:
        assert _verify(client, me, first).status_code == 400
    assert _verify(client, me, second).status_code == 200


# --- 9-10. Qayta ishlatish va poyga -------------------------------------------------


def test_code_cannot_be_replayed(client: TestClient, me: AuthenticatedUser) -> None:
    code = _code(client, me)
    assert _verify(client, me, code).status_code == 200
    assert _verify(client, me, code).status_code == 400


def test_code_bound_to_requesting_account(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    """Birovning kodi bilan raqamni o'z akkauntiga yozib bo'lmaydi."""
    code = _code(client, me)
    attacker = create_user(client, db_session, email="attacker@example.com")
    assert _verify(client, attacker, code).status_code == 400
    assert _user(db_session, attacker.id).phone_verified_at is None
    assert _verify(client, me, code).status_code == 200


def test_concurrent_verification_consumes_code_once(
    client: TestClient,
    db_session: Session,
    db_engine: Engine,
    me: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bir kod bilan ikki parallel tekshiruv: faqat bittasi o'tadi.

    Har oqim kod qatorini o'qigach ikkinchisini kutadi. `FOR UPDATE` bo'lsa ikkinchi oqim
    qatorni birinchisi commit qilmaguncha o'qiy olmaydi (kutish timeout bilan tugaydi) va kod
    ishlatilgan bo'ladi. Qulf olib tashlansa ikkalasi ham o'tadi — test yiqiladi.
    """
    code = _code(client, me)
    factory = sessionmaker(bind=db_engine, autoflush=False)
    start = threading.Barrier(2)
    loaded = threading.Barrier(2, timeout=1.5)
    original = OtpRepository.get_active_for_update

    def paused(self, user_id, purpose, now):
        row = original(self, user_id, purpose, now)
        try:
            loaded.wait()
        except threading.BrokenBarrierError:
            pass
        return row

    monkeypatch.setattr(OtpRepository, "get_active_for_update", paused)
    outcomes: list[str] = []

    def worker() -> None:
        with factory() as db:
            user = db.get(User, me.id)
            start.wait()
            try:
                OtpService(db).verify_phone_code(user, PHONE, code)
                outcomes.append("ok")
            except Exception as exc:  # noqa: BLE001 — natija turini yig'amiz
                outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["HTTPException", "ok"]
    consumed = db_session.scalar(select(OtpCode).where(OtpCode.user_id == me.id))
    assert consumed.consumed_at is not None


# --- 11. Bitta tasdiqlangan raqam = bitta faol akkaunt --------------------------------


def test_number_verified_elsewhere_is_rejected(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    _verified(db_session, owner, PHONE)
    code = _code(client, me)
    response = _verify(client, me, code)
    assert response.status_code == 409
    assert response.json()["detail"] == PHONE_TAKEN
    assert _user(db_session, me.id).phone_verified_at is None


def test_deleted_account_releases_number(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    owner = create_user(client, db_session, email="owner@example.com")
    _verified(db_session, owner, PHONE)
    row = _user(db_session, owner.id)
    row.deleted_at = datetime.now(UTC)
    db_session.commit()
    assert _verify(client, me, _code(client, me)).status_code == 200


def test_database_rejects_second_verified_holder(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    other = create_user(client, db_session, email="other@example.com")
    _verified(db_session, me, PHONE)
    with pytest.raises(IntegrityError):
        _verified(db_session, other, PHONE)
    db_session.rollback()


# --- 12-13. Raqamni almashtirish ----------------------------------------------------------


def test_profile_patch_cannot_swap_verified_phone(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    _verified(db_session, me, PHONE)
    response = client.patch("/api/v1/users/me", headers=me.headers, json={"phone": OTHER})
    assert response.status_code == 409
    user = _user(db_session, me.id)
    assert user.phone == PHONE and user.phone_verified_at is not None
    # Bir xil raqam (boshqa formatda) — o'zgarish yo'q, 200.
    same = client.patch("/api/v1/users/me", headers=me.headers, json={"phone": "90 111 22 33"})
    assert same.status_code == 200


def test_change_requires_reauthentication(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    _verified(db_session, me, PHONE)
    stale = _stale_headers(me)
    no_password = client.post(REQUEST, headers=stale, json={"phone": OTHER})
    assert no_password.status_code == 403
    assert no_password.json()["detail"] == REAUTH_REQUIRED
    wrong = client.post(REQUEST, headers=stale, json={"phone": OTHER, "password": "Wrong123"})
    assert wrong.status_code == 403
    ok = client.post(REQUEST, headers=stale, json={"phone": OTHER, "password": TEST_PASSWORD})
    assert ok.status_code == 200, ok.text


def test_change_keeps_old_number_until_new_is_verified_and_notifies(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    _verified(db_session, me, PHONE)
    code = _code(client, me, OTHER)  # yangi login (auth_time yaqin) — parolsiz
    user = _user(db_session, me.id)
    assert user.phone == PHONE and user.phone_verified_at is not None  # hali eskisi

    assert _verify(client, me, code, OTHER).status_code == 200
    user = _user(db_session, me.id)
    assert user.phone == OTHER and user.phone_verified_at is not None
    notice = db_session.scalar(
        select(Notification).where(
            Notification.user_id == me.id, Notification.type == NotificationType.PHONE_CHANGED
        )
    )
    assert notice is not None
    assert OTHER not in (notice.body or "")  # to'liq raqam yozilmaydi


def test_verifying_the_same_number_again_is_conflict(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    _verified(db_session, me, PHONE)
    assert _request(client, me, PHONE).status_code == 409


@pytest.mark.usefixtures("google_configured", "no_cooldown")
def test_google_user_verifies_and_changes_with_recent_login(client: TestClient) -> None:
    """Google foydalanuvchisi parolni bilmaydi: yaqinda kirgan bo'lsa almashtiradi."""
    login = client.post("/api/v1/auth/google", json={"credential": make_credential()})
    assert login.status_code == 200
    token = login.json()["access_token"]
    user_id = client.get("/api/v1/auth/me", headers=auth_headers(token)).json()["id"]
    google_user = AuthenticatedUser(
        id=user_id,
        email="aziza@gmail.com",
        password="",
        access_token=token,
        refresh_token="",
        headers=auth_headers(token),
    )
    assert _verify(client, google_user, _code(client, google_user)).status_code == 200
    stale = client.post(REQUEST, headers=_stale_headers(google_user), json={"phone": OTHER})
    assert stale.status_code == 403
    assert _verify(client, google_user, _code(client, google_user, OTHER), OTHER).status_code == 200


# --- 15-16. Marketplace: tasdiqsiz to'siladi, tasdiqdan keyin ruxsat --------------------


def test_marketplace_action_unlocked_by_otp(
    client: TestClient, db_session: Session, me: AuthenticatedUser
) -> None:
    seller = create_user(client, db_session, email="seller@example.com")
    _verified(db_session, seller, "+998901000001")
    item = client.post(
        "/api/v1/items",
        headers=seller.headers,
        json={"title": "Samsung Galaxy A55", "condition": "new", "starting_price": "350000000"},
    ).json()
    client.post(
        f"/api/v1/items/{item['id']}/publish", headers=seller.headers, json={"duration_days": 5}
    )
    offer = {"quantity": 1, "unit_price": "320000000"}
    url = f"/api/v1/items/{item['id']}/offers"

    blocked = client.post(url, headers=me.headers, json=offer)
    assert blocked.status_code == 403 and blocked.json()["detail"] == "phone_verification_required"
    assert _verify(client, me, _code(client, me)).status_code == 200
    # Xuddi shu access token bilan (qayta login'siz) amal endi o'tadi.
    assert client.post(url, headers=me.headers, json=offer).status_code == 201


# --- 17. Javob va log'larda sir yo'q ----------------------------------------------------


def test_production_never_returns_code(
    client: TestClient, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    sent: list[str] = []

    class Capture(LogSmsProvider):
        def send(self, phone: str, text: str) -> SmsResult:
            sent.append(text)
            return SmsResult(message_id="cap", delivered=True)

    monkeypatch.setattr(otp_module, "get_sms_provider", lambda: Capture())
    response = _request(client, me)
    assert response.status_code == 200
    assert response.json()["debug_code"] is None
    code = re.search(r"\d{6}", sent[0]).group()
    assert code not in response.text


def test_logs_never_contain_code_or_full_phone(
    client: TestClient, me: AuthenticatedUser, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        code = _code(client, me)
        _verify(client, me, "000000" if code != "000000" else "111111")
        _verify(client, me, code)
    text = caplog.text
    assert code not in text
    assert PHONE not in text and PHONE[1:] not in text


# --- 18-19. SMS provayderlari: xato, qayta urinish, prod cheklovlari ----------------------


class _Failing(LogSmsProvider):
    def send(self, phone: str, text: str) -> SmsResult:
        raise SmsDeliveryError("provider down")


def test_sms_failure_discards_code_and_allows_immediate_retry(
    client: TestClient, db_session: Session, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(otp_module, "get_sms_provider", lambda: _Failing())
    failed = _request(client, me)
    assert failed.status_code == 503
    assert failed.json()["detail"] == SMS_SEND_FAILED
    assert db_session.scalar(select(OtpCode).where(OtpCode.user_id == me.id)) is None

    monkeypatch.setattr(otp_module, "get_sms_provider", lambda: LogSmsProvider())
    assert _request(client, me).status_code == 200  # cooldown sarflanmagan


def test_null_provider_counts_as_failure(
    client: TestClient, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(otp_module, "get_sms_provider", lambda: NullSmsProvider())
    assert _request(client, me).status_code == 503


def test_log_provider_masks_code_and_phone(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        LogSmsProvider().send(PHONE, "Bazart tasdiqlash kodi: 482913. Amal qilish muddati: 5")
    assert "482913" not in caplog.text and PHONE not in caplog.text


def test_provider_registry() -> None:
    assert available_provider_names() == ["eskiz", "log", "null"]
    assert isinstance(get_sms_provider("log"), LogSmsProvider)


def test_unknown_provider_falls_back_only_outside_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert isinstance(get_sms_provider("nope"), LogSmsProvider)
    monkeypatch.setattr(settings, "environment", "production")
    with pytest.raises(SmsDeliveryError):
        get_sms_provider("nope")


@pytest.mark.parametrize(
    ("extra", "ok"),
    [
        ({}, False),  # log — prod'da taqiq
        ({"sms_provider": "null"}, False),
        ({"sms_provider": "eskiz"}, False),  # hisob ma'lumotlarisiz
        ({"sms_provider": "eskiz", "eskiz_email": "a@b.uz", "eskiz_password": "x"}, True),
    ],
)
def test_production_requires_real_sms_provider(extra: dict, ok: bool) -> None:
    base = {"environment": "production", "secret_key": "p" * 48, "psp_webhook_secret": "w" * 48}
    if ok:
        settings.__class__(_env_file=None, **base, **extra)
    else:
        with pytest.raises(ValueError, match="SMS_PROVIDER|ESKIZ"):
            settings.__class__(_env_file=None, **base, **extra)


def _eskiz(monkeypatch: pytest.MonkeyPatch, handler) -> EskizSmsProvider:
    monkeypatch.setattr(settings, "eskiz_email", "bazart@example.uz")
    monkeypatch.setattr(settings, "eskiz_password", "secret")
    monkeypatch.setattr(EskizSmsProvider, "_token", None)
    return EskizSmsProvider(transport=httpx.MockTransport(handler))


def test_eskiz_login_and_send(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.path, request.content.decode()))
        if request.url.path.endswith("/auth/login"):
            return httpx.Response(200, json={"data": {"token": "tok-1"}})
        assert request.headers["Authorization"] == "Bearer tok-1"
        return httpx.Response(200, json={"id": "msg-42", "status": "waiting"})

    result = _eskiz(monkeypatch, handler).send(PHONE, "kod 123456")
    assert result.delivered and result.message_id == "msg-42"
    send_body = calls[-1][1]
    assert "mobile_phone=998901112233" in send_body  # "+" siz


def test_eskiz_relogins_once_on_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = iter(["old", "new"])
    sends: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/login"):
            return httpx.Response(200, json={"data": {"token": next(tokens)}})
        sends.append(request.headers["Authorization"])
        if request.headers["Authorization"] == "Bearer old":
            return httpx.Response(401)
        return httpx.Response(200, json={"id": "ok"})

    assert _eskiz(monkeypatch, handler).send(PHONE, "kod").delivered
    assert sends == ["Bearer old", "Bearer new"]


def test_eskiz_retries_server_error_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/login"):
            return httpx.Response(200, json={"data": {"token": "t"}})
        attempts.append(1)
        return httpx.Response(503)

    with pytest.raises(SmsDeliveryError):
        _eskiz(monkeypatch, handler).send(PHONE, "kod")
    assert len(attempts) == 2


def test_eskiz_network_error_is_delivery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(SmsDeliveryError):
        _eskiz(monkeypatch, handler).send(PHONE, "kod")


def test_disabled_otp_returns_503(
    client: TestClient, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "otp_enabled", False)
    assert _request(client, me).status_code == 503


def test_access_token_carries_session_auth_time(client: TestClient, me: AuthenticatedUser) -> None:
    import jwt

    claims = jwt.decode(me.access_token, options={"verify_signature": False})
    assert abs(claims["auth_time"] - datetime.now(UTC).timestamp()) < 60
    legacy = create_token(str(me.id), ACCESS_TOKEN_TYPE, timedelta(minutes=5))
    assert "auth_time" not in jwt.decode(legacy, options={"verify_signature": False})


def test_otp_endpoints_have_own_ip_bucket(
    client: TestClient, me: AuthenticatedUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OTP o'z IP limitiga ega (CGNAT): register/reset ("auth") hisobini yemaydi va aksincha."""
    from app.core.rate_limit import reset_rate_limits
    from tests.conftest import freeze_rate_limit_window

    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_otp_per_minute", 2)
    monkeypatch.setattr(settings, "otp_resend_cooldown_seconds", 0)
    freeze_rate_limit_window(monkeypatch)
    reset_rate_limits()

    assert _request(client, me).status_code == 200
    assert _verify(client, me, "000000").status_code in (200, 400)
    assert _request(client, me).status_code == 429
    # "auth" bucket alohida — parolni tiklash so'rovi o'tadi.
    assert client.post("/api/v1/auth/forgot-password", json={"email": me.email}).status_code == 200
