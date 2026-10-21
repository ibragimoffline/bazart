"""Oddiy process-ichi (in-memory) rate limiter.

Login va bid endpointlarini brute-force / spam'dan himoya qiladi. Har mijoz
(IP bo'yicha) belgilangan oyna (window) ichida cheklangan sondagi so'rov qila
oladi; oshsa `429 Too Many Requests` qaytadi.

Nega settings chaqiruv paytida o'qiladi (import paytida emas): shunda testlar
`monkeypatch.setattr(settings, ...)` bilan muhit va limitlarni o'zgartira oladi.

TODO(kelajak): bu limiter faqat bitta process ichida to'g'ri ishlaydi. Bir
nechta uvicorn worker (yoki bir nechta instans) ishlaganda har biri o'z
hisobini alohida yuritadi — real limit worker soniga ko'payadi. Ishlab
chiqarishda umumiy holat uchun Redis (sliding-window yoki token-bucket) kerak.
"""

from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis_client import get_redis

# (identifier, scope) -> shu oynadagi so'rov vaqtlari (monotonic sekundlar).
_hits: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()

# scope -> qaysi settings maydonidan limit o'qilishi. Limit qiymati chaqiruv
# paytida shu jadval orqali olinadi, import paytida qotib qolmaydi.
_SCOPE_LIMIT_SETTING: dict[str, str] = {
    "login": "rate_limit_login_per_minute",
    # register / forgot / reset — login bilan BIR XIL limit qiymati, lekin
    # ALOHIDA bucket (bucket kaliti scope'ni o'z ichiga oladi), shunda ular
    # login brute-force hisobiga aralashmaydi.
    "auth": "rate_limit_login_per_minute",
    "bid": "rate_limit_bid_per_minute",
    # Telefon OTP — alohida va kengroq: mobil operatorlar ko'p foydalanuvchini bitta IP
    # ortida (CGNAT) chiqaradi. Asosiy himoya — kod/raqam/akkaunt/kunlik limitlar (OtpService).
    "otp": "rate_limit_otp_per_minute",
}


def reset_rate_limits() -> None:
    """Barcha hisoblangan holatni tozalaydi (testlar orasida ishlatiladi).

    Ham in-memory zaxira, ham Redis fixed-window kalitlari (`ratelimit:*`)
    tozalanadi. Redis yoqilgan muhitda faqat in-memory'ni tozalash yetarli emas:
    bucket testlar orasida saqlanib, keyingi test yolg'on 429 oladi.
    """
    with _lock:
        _hits.clear()
    client = get_redis()
    if client is not None:
        try:
            keys = list(client.scan_iter(match="ratelimit:*"))
            if keys:
                client.delete(*keys)
        except Exception:
            # Redis muammosi tozalashni bloklamasin — in-memory allaqachon tozalandi.
            pass


def _identifier(request: Request) -> str:
    """Mijozni IP bo'yicha aniqlaydi; aniqlab bo'lmasa 'unknown'.

    Reverse proxy (nginx/ALB) ortida `request.client.host` proxy'ning IP'si
    bo'ladi — o'shanda BARCHA mijoz bitta IP'ga tushib, limit global bo'lib
    qoladi. Buning oldini olish uchun `X-Forwarded-For` bo'lsa, undagi BIRINCHI
    IP (asl mijoz) ishlatiladi.

    OGOHLANTIRISH: `X-Forwarded-For` mijoz tomonidan soxtalashtirilishi mumkin
    (spoofing). Unga faqat ISHONCHLI proxy ortida ishonish kerak — proxy
    sarlavhani qayta yozib, soxta qiymatni almashtiradi.
    TODO(kelajak): ishonchli proxy IP ro'yxatini sozlash va faqat o'shalardan
    kelgan XFF'ga ishonish.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


class RateLimiter:
    """FastAPI dependency: bitta scope uchun mijoz IP'iga oyna bo'yicha limit.

    scope orqali qaysi settings maydonidan limit olishni biladi (masalan
    scope="login" -> `settings.rate_limit_login_per_minute`). Limit qiymati
    dependency chaqirilganda o'qiladi, shuning uchun test monkeypatch qila oladi.
    """

    def __init__(self, scope: str, window_seconds: int = 60) -> None:
        if scope not in _SCOPE_LIMIT_SETTING:
            raise ValueError(f"Noma'lum rate-limit scope: {scope!r}")
        self.scope = scope
        self.window_seconds = window_seconds

    def _limit(self) -> int:
        """Joriy limitni settings'dan (chaqiruv paytida) o'qiydi."""
        return getattr(settings, _SCOPE_LIMIT_SETTING[self.scope])

    def __call__(self, request: Request) -> None:
        # Limiter faqat yoqilgan va NON-test muhitda ishlaydi. Aks holda no-op:
        # test to'plami ko'p marta login/bid qiladi, ular 429 olmasligi kerak.
        if not settings.rate_limit_enabled or settings.environment == "test":
            return

        limit = self._limit()
        identifier = _identifier(request)

        # Redis bor bo'lsa — barcha worker'lar orasida umumiy limit. Aks holda
        # process-ichi in-memory zaxira (bitta worker uchun to'g'ri).
        if not _redis_allow(self.scope, identifier, limit, self.window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Juda ko'p so'rov. Birozdan keyin qayta urinib ko'ring.",
            )
        if not _memory_allow(self.scope, identifier, limit, self.window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Juda ko'p so'rov. Birozdan keyin qayta urinib ko'ring.",
            )


def _redis_allow(scope: str, identifier: str, limit: int, window: int) -> bool:
    """Redis fixed-window hisoblagich. Redis yo'q bo'lsa True (zaxiraga o'tadi).

    Kalit oynaga bog'lanadi (`...:<bucket>`); birinchi INCR'da EXPIRE beriladi,
    oyna tugagach kalit avtomatik o'chadi. Limitdan oshsa False.
    """
    client = get_redis()
    if client is None:
        return True
    try:
        bucket = int(time.time()) // window
        key = f"ratelimit:{scope}:{identifier}:{bucket}"
        count = client.incr(key)
        if count == 1:
            client.expire(key, window)
        return count <= limit
    except Exception:
        # Redis ishlamay qoldi — limitni bloklamaymiz, in-memory hal qiladi.
        return True


def _memory_allow(scope: str, identifier: str, limit: int, window: int) -> bool:
    """Process-ichi sliding-window zaxira (Redis yo'q yoki ishlamaganda)."""
    if get_redis() is not None:
        # Redis faol — ikkilamchi hisoblash shart emas.
        return True
    key = (identifier, scope)
    now = time.monotonic()
    window_start = now - window
    with _lock:
        hits = _hits.setdefault(key, [])
        hits[:] = [ts for ts in hits if ts > window_start]
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True
