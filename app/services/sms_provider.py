"""SMS provayderi — ulanadigan abstraksiya (push_provider naqshi).

OTP kodini SMS orqali yetkazish uchun YAGONA interfeys. Provayder nomi sozlamada
(`SMS_PROVIDER`); provayderga xos mantiq faqat shu modulda.

- `log`   — local/test: SMS yuborilmaydi, log'ga yoziladi (kod NIQOBLANADI).
- `null`  — kanal o'chiq (delivered=False).
- `eskiz` — Eskiz.uz (O'zbekiston), `ESKIZ_*` sozlamalari bilan.

Prod/staging'da faqat haqiqiy provayder ruxsat etiladi (`config.py` validatori):
log/null yoki noma'lum nom bilan ilova ko'tarilmaydi. Non-prod'da noma'lum nom log'ga
tushadi (ogohlantirish bilan) — local ishlab chiqish to'xtab qolmasin.

Xatoda provayder `SmsDeliveryError` ko'taradi; OTP xizmati kodni bekor qilib, foydalanuvchiga
qayta urinish imkonini beradi. SMS matni (kod bilan) hech qachon log'ga yozilmaydi.
"""

import logging
import re
import threading
from abc import ABC, abstractmethod
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

_DIGIT_RUN = re.compile(r"\d{4,}")


def mask_phone(phone: str) -> str:
    """Log uchun: +998901234567 -> +99890*****67 (raqam to'liq yozilmaydi)."""
    if len(phone) < 8:
        return "***"
    return phone[:6] + "*" * (len(phone) - 8) + phone[-2:]


def mask_secrets(text: str) -> str:
    """Matndagi 4+ xonali raqamlarni (OTP kodi) yulduzcha bilan almashtiradi."""
    return _DIGIT_RUN.sub(lambda m: "*" * len(m.group()), text)


class SmsDeliveryError(Exception):
    """SMS provayderga topshirilmadi (tarmoq, provayder xatosi, noto'g'ri sozlama)."""


class SmsResult:
    """SMS yuborish natijasi.

    :param message_id: provayder bergan xabar identifikatori (audit/kuzatuv uchun).
    :param delivered: xabar yetkazishga topshirildimi.
    """

    def __init__(self, message_id: str, delivered: bool) -> None:
        self.message_id = message_id
        self.delivered = delivered


class BaseSmsProvider(ABC):
    """SMS provayderlari uchun umumiy shartnoma."""

    provider_name: str

    @abstractmethod
    def send(self, phone: str, text: str) -> SmsResult:
        """Berilgan raqamga SMS matnini yuboradi.

        :param phone: qabul qiluvchi telefon raqami (E.164, masalan +998901234567).
        :param text: SMS matni (OTP kodi bilan).
        :raises SmsDeliveryError: xabar provayderga topshirilmasa.
        """
        raise NotImplementedError


class LogSmsProvider(BaseSmsProvider):
    """Local/test uchun: SMS haqiqatan yuborilmaydi, faqat log'ga yoziladi.

    Kod log'da NIQOBLANADI — log yig'ish tizimiga (ELK, Sentry) kod tushmasin. Local'da
    kod API javobidagi `debug_code` orqali olinadi (faqat non-prod).
    """

    provider_name = "log"

    def send(self, phone: str, text: str) -> SmsResult:
        message_id = f"log_{uuid4().hex}"
        logger.info(
            "sms[%s] -> phone=%s text=%r", message_id, mask_phone(phone), mask_secrets(text)
        )
        return SmsResult(message_id=message_id, delivered=True)


class NullSmsProvider(BaseSmsProvider):
    """SMS'ni butunlay o'chiruvchi provayder: hech narsa yubormaydi.

    delivered=False qaytaradi — kanal mavjud, lekin faol emas holatida.
    """

    provider_name = "null"

    def send(self, phone: str, text: str) -> SmsResult:
        return SmsResult(message_id=f"null_{uuid4().hex}", delivered=False)


class EskizSmsProvider(BaseSmsProvider):
    """Eskiz.uz SMS shlyuzi (https://notify.eskiz.uz).

    Avtorizatsiya: `POST /auth/login` (email + parol) -> Bearer token; token process ichida
    keshlanadi va 401 da bir marta yangilanadi. Yuborish: `POST /message/sms/send`
    (`mobile_phone` — "+" siz, `message`, `from` — tasdiqlangan jo'natuvchi nomi).
    Tarmoq xatosi yoki 5xx bo'lsa bir marta qayta uriniladi.

    Prod'da Eskiz OTP matni shablonini oldindan tasdiqlaydi — matn
    `OtpService` dagi shablon bilan aynan mos bo'lishi kerak.
    """

    provider_name = "eskiz"
    _token: str | None = None
    _token_lock = threading.Lock()

    def __init__(self, transport=None) -> None:
        # transport — faqat test uchun (httpx.MockTransport). Prod'da None.
        self._transport = transport
        self._base = settings.eskiz_base_url.rstrip("/")

    def _client(self):
        import httpx

        return httpx.Client(timeout=settings.sms_timeout_seconds, transport=self._transport)

    def _login(self) -> str:
        import httpx

        try:
            with self._client() as http:
                response = http.post(
                    f"{self._base}/auth/login",
                    data={"email": settings.eskiz_email, "password": settings.eskiz_password},
                )
        except httpx.HTTPError as exc:
            raise SmsDeliveryError(f"Eskiz login tarmoq xatosi: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise SmsDeliveryError(f"Eskiz login rad etildi: HTTP {response.status_code}")
        token = (response.json().get("data") or {}).get("token")
        if not token:
            raise SmsDeliveryError("Eskiz login javobida token yo'q")
        EskizSmsProvider._token = token
        return token

    def _token_value(self, refresh: bool = False) -> str:
        with EskizSmsProvider._token_lock:
            if refresh or EskizSmsProvider._token is None:
                return self._login()
            return EskizSmsProvider._token

    def send(self, phone: str, text: str) -> SmsResult:
        import httpx

        payload = {
            "mobile_phone": phone.removeprefix("+"),
            "message": text,
            "from": settings.eskiz_sender,
        }
        token = self._token_value()
        last_error = "noma'lum xato"
        for attempt in range(2):
            try:
                with self._client() as http:
                    response = http.post(
                        f"{self._base}/message/sms/send",
                        data=payload,
                        headers={"Authorization": f"Bearer {token}"},
                    )
            except httpx.HTTPError as exc:
                last_error = f"tarmoq xatosi: {type(exc).__name__}"
                continue
            if response.status_code == 401 and attempt == 0:
                token = self._token_value(refresh=True)
                continue
            if response.status_code >= 500:
                last_error = f"HTTP {response.status_code}"
                continue
            if response.status_code not in (200, 201):
                raise SmsDeliveryError(f"Eskiz SMS rad etildi: HTTP {response.status_code}")
            message_id = str(response.json().get("id") or f"eskiz_{uuid4().hex}")
            return SmsResult(message_id=message_id, delivered=True)
        raise SmsDeliveryError(f"Eskiz SMS yuborilmadi ({last_error})")


_PROVIDERS: dict[str, type[BaseSmsProvider]] = {
    LogSmsProvider.provider_name: LogSmsProvider,
    NullSmsProvider.provider_name: NullSmsProvider,
    EskizSmsProvider.provider_name: EskizSmsProvider,
}


def available_provider_names() -> list[str]:
    """Ro'yxatga olingan SMS provayder nomlari."""
    return sorted(_PROVIDERS)


def get_sms_provider(name: str | None = None) -> BaseSmsProvider:
    """Nom bo'yicha SMS provayderini qaytaradi (default: settings.sms_provider).

    Non-prod'da noma'lum nom log provayderiga tushadi (ogohlantirish bilan). Prod'da bu holat
    ilova ishga tushishida `config.py` validatori bilan to'siladi; shunga qaramay bu yerga
    yetib kelsa — kod log'ga tushib qolmasin deb xato ko'tariladi.
    """
    provider_key = name or settings.sms_provider
    provider_cls = _PROVIDERS.get(provider_key)
    if provider_cls is None:
        if settings.is_production:
            raise SmsDeliveryError(f"Noma'lum SMS provayderi: {provider_key!r}")
        logger.warning(
            "Noma'lum SMS provayderi: %r. Log provayderiga tushildi. Mavjudlari: %s",
            provider_key,
            available_provider_names(),
        )
        provider_cls = LogSmsProvider
    return provider_cls()
