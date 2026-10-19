"""OTP (telefon tasdiqlash / SMS) testlari.

Testlar "test" muhitida ishlaydi: rate limiting o'chiq, is_production False —
shu sababli `/auth/otp/request` javobida `debug_code` qaytadi (verify uchun
kodni SMS log'idan qidirmasdan olamiz).

ESLATMA: bu fayl faqat yoziladi, ISHGA TUSHIRILMAYDI (orkestrator qoidasi).
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.otp import OtpCode
from app.models.user import User
from app.services.otp_service import _hash_code
from app.services.sms_provider import (
    BaseSmsProvider,
    LogSmsProvider,
    NullSmsProvider,
    SmsResult,
    available_provider_names,
    get_sms_provider,
)

PHONE = "+998901112233"

# Telefon tasdig'i sinovlari tasdiqlanmagan foydalanuvchidan boshlanadi.
pytestmark = pytest.mark.usefixtures("unverified_phones")


def _request_otp(client: TestClient, phone: str = PHONE, purpose: str = "phone_verify") -> dict:
    response = client.post(
        "/api/v1/auth/otp/request",
        json={"phone": phone, "purpose": purpose},
    )
    return response


# --- SMS provider (sof birlik testlari, DB kerak emas) ---------------------


def test_log_sms_provider_delivers():
    result = LogSmsProvider().send("+998901112233", "kod: 123456")
    assert isinstance(result, SmsResult)
    assert result.delivered is True
    assert result.message_id.startswith("log_")


def test_null_sms_provider_not_delivered():
    assert NullSmsProvider().send("+998901112233", "x").delivered is False


def test_get_sms_provider_defaults_to_settings():
    provider = get_sms_provider()
    assert isinstance(provider, BaseSmsProvider)


def test_get_sms_provider_unknown_falls_back_to_log():
    # Graceful: noma'lum provayder ilovani yiqitmaydi — log'ga tushadi.
    provider = get_sms_provider("nomalum-provider")
    assert isinstance(provider, LogSmsProvider)


def test_available_sms_provider_names_sorted():
    names = available_provider_names()
    assert "log" in names
    assert names == sorted(names)


# --- Request -> verify oqimi -----------------------------------------------


def test_otp_request_and_verify_flow(client: TestClient):
    request_response = _request_otp(client)
    assert request_response.status_code == 200
    body = request_response.json()
    assert "expires_at" in body
    code = body["debug_code"]
    assert code is not None
    assert len(code) == settings.otp_code_length

    verify_response = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["verified"] is True


def test_otp_code_is_hashed_not_plaintext(client: TestClient, db_session: Session):
    body = _request_otp(client).json()
    code = body["debug_code"]

    otp = db_session.scalar(select(OtpCode).where(OtpCode.phone == PHONE))
    assert otp is not None
    # Xom kod DBda saqlanmaydi — faqat hash. Hash mos kelishi kerak.
    assert otp.code_hash != code
    assert otp.code_hash == _hash_code(code)


def test_otp_verify_wrong_code_rejected(client: TestClient):
    _request_otp(client)
    response = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": "000000", "purpose": "phone_verify"},
    )
    # 000000 debug_code ga teng bo'lib qolishi ehtimoli 1e-6 — deyarli imkonsiz.
    assert response.status_code == 400


def test_otp_verify_consumed_code_cannot_be_reused(client: TestClient):
    code = _request_otp(client).json()["debug_code"]
    first = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert first.status_code == 200
    # Ikkinchi marta o'sha kod — endi faol kod yo'q (consumed) -> 400.
    second = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert second.status_code == 400


# --- Cheklovlar -------------------------------------------------------------


def test_otp_resend_cooldown(client: TestClient):
    first = _request_otp(client)
    assert first.status_code == 200
    # Cooldown ichida darhol ikkinchi so'rov -> 429.
    second = _request_otp(client)
    assert second.status_code == 429


def test_otp_max_attempts_blocks(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "otp_max_attempts", 3)
    _request_otp(client)

    for _ in range(3):
        wrong = client.post(
            "/api/v1/auth/otp/verify",
            json={"phone": PHONE, "code": "000000", "purpose": "phone_verify"},
        )
        assert wrong.status_code == 400

    # 3 noto'g'ri urinishdan keyin kod bloklanadi -> 429 (400 emas).
    blocked = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": "000000", "purpose": "phone_verify"},
    )
    assert blocked.status_code == 429


def test_otp_expired_code_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # TTL=0 -> kod yaratilishi bilanoq muddati o'tadi (expires_at > now yolg'on).
    monkeypatch.setattr(settings, "otp_ttl_seconds", 0)
    code = _request_otp(client).json()["debug_code"]

    response = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert response.status_code == 400


def test_otp_daily_limit_per_phone(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    # Cooldownni o'chirib, kunlik raqam limitini past qo'yamiz.
    monkeypatch.setattr(settings, "otp_resend_cooldown_seconds", 0)
    monkeypatch.setattr(settings, "otp_daily_limit_per_phone", 2)

    assert _request_otp(client).status_code == 200
    assert _request_otp(client).status_code == 200
    # Uchinchi so'rov limitdan oshadi -> 429.
    assert _request_otp(client).status_code == 429


def test_otp_disabled_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "otp_enabled", False)
    assert _request_otp(client).status_code == 503


# --- PHONE_VERIFY foydalanuvchini tasdiqlaydi ------------------------------


def test_phone_verify_marks_user(client: TestClient, db_session: Session, test_user):
    # Foydalanuvchiga telefon raqam biriktiramiz (registratsiyada yo'q edi).
    user = db_session.get(User, test_user.id)
    user.phone = PHONE
    db_session.add(user)
    db_session.commit()

    code = _request_otp(client).json()["debug_code"]
    verify_response = client.post(
        "/api/v1/auth/otp/verify",
        headers=test_user.headers,
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["phone_verified"] is True

    db_session.refresh(user)
    assert user.phone_verified_at is not None
    assert user.phone_verified_at <= datetime.now(UTC)


def test_verify_without_matching_user_still_succeeds(client: TestClient):
    # Raqam hech kimga bog'lanmagan bo'lsa ham kod tasdiqlanadi (registratsiya
    # oqimi), lekin phone_verified False (belgilaydigan foydalanuvchi yo'q).
    code = _request_otp(client).json()["debug_code"]
    response = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["phone_verified"] is False


def _set_phone(db_session: Session, user_id: int, phone: str) -> User:
    user = db_session.get(User, user_id)
    user.phone = phone
    db_session.add(user)
    db_session.commit()
    return user


def test_anonymous_verify_does_not_mark_any_user(
    client: TestClient, db_session: Session, test_user
) -> None:
    """Login'siz tasdiq raqami shu bo'lgan akkauntni belgilamaydi (faqat so'rovchi)."""
    user = _set_phone(db_session, test_user.id, PHONE)
    code = _request_otp(client).json()["debug_code"]
    response = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert response.status_code == 200
    assert response.json()["phone_verified"] is False
    db_session.refresh(user)
    assert user.phone_verified_at is None


def test_verify_marks_only_requester_not_other_holder(
    client: TestClient, db_session: Session, test_user, test_seller
) -> None:
    """Ikki akkauntda bir xil raqam: kodni kiritgan (login qilgan) tasdiqlanadi, boshqasi yo'q."""
    other = _set_phone(db_session, test_user.id, PHONE)
    me = _set_phone(db_session, test_seller.id, PHONE)
    code = _request_otp(client).json()["debug_code"]
    response = client.post(
        "/api/v1/auth/otp/verify",
        headers=test_seller.headers,
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert response.json()["phone_verified"] is True
    db_session.refresh(other)
    db_session.refresh(me)
    assert me.phone_verified_at is not None
    assert other.phone_verified_at is None


def test_phone_verified_on_another_account_is_rejected(
    client: TestClient, db_session: Session, test_user, test_seller
) -> None:
    """Bitta raqam = bitta tasdiqlangan akkaunt: ikkinchisi 409 oladi."""
    owner = _set_phone(db_session, test_user.id, PHONE)
    owner.phone_verified_at = datetime.now(UTC)
    db_session.commit()
    _set_phone(db_session, test_seller.id, PHONE)
    code = _request_otp(client).json()["debug_code"]
    response = client.post(
        "/api/v1/auth/otp/verify",
        headers=test_seller.headers,
        json={"phone": PHONE, "code": code, "purpose": "phone_verify"},
    )
    assert response.status_code == 409
