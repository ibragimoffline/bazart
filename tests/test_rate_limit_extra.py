"""Rate limiting'ning kengaytmasi uchun testlar.

Bu yerda ikki narsa sinovdan o'tadi:
1. `register` va `reset-password` endpointlari "login" scope bilan
   himoyalangan (sezgir endpointlar — brute-force / spam nishoni).
2. Identifikator `X-Forwarded-For` sarlavhasini hisobga oladi — reverse proxy
   ortida har mijoz alohida hisoblanadi, hammasi bitta proxy IP'ga tushmaydi.

Mavjud test to'plami "test" muhitida ishlaydi va limiter o'chiq bo'ladi. Bu
testlar limiter'ni ATAYLAB yoqadi: muhitni "local" ga o'zgartiradi, kichik
limit qo'yadi va har test boshida hisoblagichni tozalaydi.
"""

from conftest import TEST_PASSWORD, freeze_rate_limit_window
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import reset_rate_limits


def _enable_limiter(monkeypatch, *, limit: int = 3) -> None:
    """Limiter'ni yoqadi: NON-test muhit + enabled + kichik login limiti."""
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_login_per_minute", limit)
    freeze_rate_limit_window(monkeypatch)
    reset_rate_limits()


def _register_payload(email: str) -> dict[str, str]:
    return {"email": email, "password": TEST_PASSWORD, "full_name": email.split("@")[0]}


def test_register_over_limit_429(client: TestClient, monkeypatch) -> None:
    """Bir xil IP'dan limitdan oshiq register 429 oladi.

    Har so'rov noyob email bilan (register muvaffaqiyatli 201 bo'lsin), lekin
    IP bir xil — shuning uchun hammasi bitta bucket'ga tushadi.
    """
    _enable_limiter(monkeypatch, limit=3)

    statuses = []
    for i in range(5):
        response = client.post(
            "/api/v1/auth/register",
            json=_register_payload(f"ratelimit-register-{i}@example.com"),
        )
        statuses.append(response.status_code)

    # Limit=3: 1-3 urinish o'tadi (201), 4-urinishdan boshlab 429.
    assert statuses[:3] == [201, 201, 201]
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_reset_password_over_limit_429(client: TestClient, monkeypatch) -> None:
    """Limitdan oshiq reset-password so'rovi 429 oladi.

    429 endpoint mantig'idan (token tekshiruvi) OLDIN, dependency bosqichida
    ishga tushadi. Shuning uchun token yaroqsiz bo'lsa ham, limitdan oshsa 429
    keladi — limit-ostidagi urinishlar esa 429 EMAS.
    """
    _enable_limiter(monkeypatch, limit=3)

    body = {"token": "invalid-token", "new_password": "Password1"}
    statuses = []
    for _ in range(5):
        response = client.post("/api/v1/auth/reset-password", json=body)
        statuses.append(response.status_code)

    # Limit-ostidagi 3 urinish 429 EMAS (yaroqsiz token uchun boshqa xato).
    assert all(code != 429 for code in statuses[:3])
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_x_forwarded_for_buckets_are_separate(client: TestClient, monkeypatch) -> None:
    """Ikki xil X-Forwarded-For IP alohida hisoblanadi.

    Reverse proxy ortida `request.client.host` proxy IP'si bo'ladi; XFF
    ishlatilmasa BARCHA mijoz bitta bucket'ga tushib, limit global bo'lardi.
    Bu test XFF birinchi IP'si bo'yicha ajratilishini tasdiqlaydi.
    """
    _enable_limiter(monkeypatch, limit=3)

    # 9.9.9.9 mijozini limitgacha va undan oshirib chaqiramiz.
    hot_ip = {"X-Forwarded-For": "9.9.9.9"}
    statuses = []
    for i in range(5):
        response = client.post(
            "/api/v1/auth/register",
            json=_register_payload(f"ratelimit-xff-hot-{i}@example.com"),
            headers=hot_ip,
        )
        statuses.append(response.status_code)

    assert statuses[3] == 429  # 9.9.9.9 limitdan oshdi

    # Boshqa XFF IP (8.8.8.8) — alohida bucket, hali OK bo'lishi kerak.
    other_ip = {"X-Forwarded-For": "8.8.8.8"}
    response = client.post(
        "/api/v1/auth/register",
        json=_register_payload("ratelimit-xff-other@example.com"),
        headers=other_ip,
    )
    assert response.status_code == 201


def test_x_forwarded_for_uses_first_ip(client: TestClient, monkeypatch) -> None:
    """XFF zanjiridagi BIRINCHI IP (asl mijoz) ishlatiladi.

    Proxy zanjiri "client, proxy1, proxy2" ko'rinishida bo'ladi; identifikator
    birinchi (asl mijoz) IP'ga bog'lanishi kerak. Bir xil birinchi IP, turli
    proxy quyruqlari — bitta bucket.
    """
    _enable_limiter(monkeypatch, limit=3)

    statuses = []
    for i in range(5):
        response = client.post(
            "/api/v1/auth/register",
            json=_register_payload(f"ratelimit-xff-first-{i}@example.com"),
            # Birinchi IP bir xil (7.7.7.7), quyruq har safar boshqacha.
            headers={"X-Forwarded-For": f"7.7.7.7, 10.0.0.{i}"},
        )
        statuses.append(response.status_code)

    # Birinchi IP bir xil bo'lgani uchun hammasi bitta bucket'ga tushadi.
    assert statuses[3] == 429
    assert statuses[4] == 429
