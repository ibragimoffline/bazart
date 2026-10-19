"""Telegram bildirishnoma provayderi — ulanadigan abstraksiya (PSP naqshi).

O'zbekistonda Telegram — asosiy bildirishnoma kanali (push o'rnida): "stavkangiz
oshib ketdi" kabi xabarlar bevosita botdan yetkaziladi. Modul ikki
implementatsiya beradi:

- `HttpTelegramProvider` — real Bot API (`sendMessage`) orqali yuboradi.
- `LogTelegramProvider` — hech narsa yubormaydi, faqat log'ga yozadi (local/test,
  yoki token sozlanmagan holat).

Tanlov `get_telegram_provider()` da: `telegram_enabled` va token bo'lsa Http, aks
holda Log. Har qanday xato YUTILADI (best-effort) — bildirishnoma yetkazilmasa
ham foydalanuvchi biznes-oqimi (bid, kelishuv) bloklanmaydi.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseTelegramProvider(ABC):
    """Telegram yetkazuvchilar uchun umumiy shartnoma."""

    provider_name: str

    @abstractmethod
    def send_message(self, chat_id: str, text: str) -> bool:
        """Berilgan chat'ga xabar yuboradi.

        Best-effort: hech qachon istisno ko'tarmaydi — yetkazildi (True) yoki
        yo'q (False) qaytaradi. Chaqiruvchi oqim bloklanmaydi.
        """
        raise NotImplementedError


class LogTelegramProvider(BaseTelegramProvider):
    """Local/test uchun: xabarni haqiqatan yubormaydi, faqat log'ga yozadi.

    Token sozlanmaganda ham shu provayder ishlatiladi — ilova yiqilmaydi.
    """

    provider_name = "log"

    def send_message(self, chat_id: str, text: str) -> bool:
        logger.info("telegram(log) -> chat_id=%s text=%r", chat_id, text)
        return True


class HttpTelegramProvider(BaseTelegramProvider):
    """Real Telegram Bot API adapteri: `POST /bot{token}/sendMessage`.

    Xato (tarmoq, 4xx/5xx) YUTILADI — best-effort. Bildirishnoma yetkazilmasligi
    biznes-oqimni to'xtatmaydi, shuning uchun False qaytariladi, istisno emas.
    """

    provider_name = "http"

    def __init__(self, *, token: str, timeout: float, transport=None) -> None:
        # transport — faqat test uchun (httpx.MockTransport). Prod'da None.
        self._token = token
        self._timeout = timeout
        self._transport = transport

    def send_message(self, chat_id: str, text: str) -> bool:
        import httpx

        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as http:
                response = http.post(url, json={"chat_id": chat_id, "text": text})
        except httpx.HTTPError as exc:
            # Tarmoq xatosi — yutamiz (best-effort), oqimni bloklamaymiz.
            logger.warning("Telegram yuborishda tarmoq xatosi: %s", exc)
            return False

        if response.status_code >= 400:
            logger.warning("Telegram %s qaytardi: %s", response.status_code, response.text[:200])
            return False
        return True


def get_telegram_provider() -> BaseTelegramProvider:
    """Joriy sozlamaga ko'ra Telegram provayderini qaytaradi.

    `telegram_enabled` yoqilgan va token berilgan bo'lsa — real HTTP provayder,
    aks holda Log provayder (graceful fallback: ilova hech qachon yiqilmaydi).
    """
    if settings.telegram_enabled and settings.telegram_bot_token:
        return HttpTelegramProvider(
            token=settings.telegram_bot_token,
            timeout=settings.telegram_api_timeout_seconds,
        )
    return LogTelegramProvider()
