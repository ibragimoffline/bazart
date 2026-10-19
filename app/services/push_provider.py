"""Push bildirishnoma provayderi — ulanadigan abstraksiya.

Hozir bildirishnoma faqat in-app (DB, notification_service). Bu modul push
(FCM/APNs) uchun YAGONA interfeys beradi — real provayder keyin ulanadi.

Naqsh: ABC + registry + get_* (sms_provider bilan bir xil).

INTEGRATSIYA (TODO):
    Real FCM/APNs adapteri `BasePushProvider` ni implement qiladi va `_PROVIDERS`
    registriga qo'shiladi. Chaqiruv nuqtasi — `notification_service.create()`:
    in-app yozuv DB'ga tushgach, foydalanuvchining qurilma token'lariga push
    yuborish uchun `get_push_provider(...).send(...)` chaqiriladi. Bu bosqichda
    modul hech joyga ULANMAGAN (mustaqil), integratsiya alohida ish.
"""

import logging
from abc import ABC, abstractmethod
from uuid import uuid4

logger = logging.getLogger(__name__)


class PushProviderError(RuntimeError):
    """Push provayderini tanlash/ishlatishda konfiguratsiya xatosi."""


class PushResult:
    """Push yuborish natijasi.

    :param message_id: provayder bergan xabar identifikatori (audit/kuzatuv uchun).
    :param delivered: provayder xabarni qabul qildimi (yetkazishga topshirildi).
    """

    def __init__(self, message_id: str, delivered: bool) -> None:
        self.message_id = message_id
        self.delivered = delivered


class BasePushProvider(ABC):
    """Push provayderlari uchun umumiy shartnoma.

    Real FCM/APNs adapteri shu interfeysni implement qiladi.
    """

    provider_name: str

    @abstractmethod
    def send(
        self,
        *,
        user_id: int,
        title: str,
        body: str | None,
        data: dict | None,
    ) -> PushResult:
        """Foydalanuvchiga push yuboradi.

        :param user_id: qabul qiluvchi foydalanuvchi (uning qurilma token'lariga).
        :param title: bildirishnoma sarlavhasi.
        :param body: matn tanasi (ixtiyoriy).
        :param data: qo'shimcha yuk — deep-link/meta (ixtiyoriy).
        """
        raise NotImplementedError


class LogPushProvider(BasePushProvider):
    """Local/test uchun: push'ni haqiqatan yubormaydi, faqat log'ga yozadi.

    Real FCM/APNs o'rniga ishlatiladi — tashqi tarmoq chaqiruvi yo'q.
    Doim delivered=True qaytaradi.
    """

    provider_name = "log"

    def send(
        self,
        *,
        user_id: int,
        title: str,
        body: str | None,
        data: dict | None,
    ) -> PushResult:
        message_id = f"log_{uuid4().hex}"
        logger.info(
            "push[%s] -> user_id=%s title=%r body=%r data=%r",
            message_id,
            user_id,
            title,
            body,
            data,
        )
        return PushResult(message_id=message_id, delivered=True)


class NullPushProvider(BasePushProvider):
    """Push'ni butunlay o'chiruvchi provayder: hech narsa yubormaydi.

    delivered=False qaytaradi — push kanali mavjud, lekin faol emas holatida
    ishlatiladi (masalan, muhitda push o'chirilgan).
    """

    provider_name = "null"

    def send(
        self,
        *,
        user_id: int,
        title: str,
        body: str | None,
        data: dict | None,
    ) -> PushResult:
        return PushResult(message_id=f"null_{uuid4().hex}", delivered=False)


# Real provayderlar (FCM/APNs) shu registrga qo'shiladi.
# TODO: real push adapterlari — notification_service.create() dan keyin chaqiriladi.
_PROVIDERS: dict[str, type[BasePushProvider]] = {
    LogPushProvider.provider_name: LogPushProvider,
    NullPushProvider.provider_name: NullPushProvider,
}


def available_provider_names() -> list[str]:
    """Ro'yxatga olingan push provayder nomlari."""
    return sorted(_PROVIDERS)


def get_push_provider(name: str) -> BasePushProvider:
    """Nom bo'yicha push provayderini qaytaradi.

    Noma'lum nom uchun XATO beradi — jimgina "hech narsa qilmaydigan"
    provayderga tushib qolmaslik uchun (aks holda push jimgina yo'qoladi).

    :raises PushProviderError: nom noma'lum.
    """
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise PushProviderError(
            f"Noma'lum push provayderi: {name!r}. Mavjudlari: {available_provider_names()}"
        )
    return provider_cls()
