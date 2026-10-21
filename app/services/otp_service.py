"""Telefonni OTP (SMS kodi) bilan tasdiqlash va almashtirish — docs/AUTH.md "Telefon tasdig'i".

Xavfsizlik tamoyillari:
  - Xom kod DBda saqlanmaydi — faqat HMAC-SHA256 hash (`settings.secret_key`); solishtirish
    `hmac.compare_digest` bilan; kod `secrets` bilan generatsiya qilinadi.
  - Kod AKKAUNTGA bog'langan (`otp_codes.user_id`): uni faqat so'ragan foydalanuvchi
    tasdiqlay oladi va tasdiq raqamni aynan shu akkauntga yozadi.
  - Tekshiruv atomik: kod qatori `FOR UPDATE` bilan qulflanadi — bir kod ikki marta
    ishlatilmaydi, urinishlar hisobi yo'qolmaydi. Yangi kod eskilarini bekor qiladi.
  - Cheklovlar: resend cooldown (raqam va akkaunt), kunlik raqam/IP/akkaunt limitlari,
    urinishlar soni — SMS bombing va brute-force himoyasi.
  - Tasdiqlangan raqamni almashtirish — joriy parol yoki yaqinda login (qayta autentifikatsiya).
  - Kod, to'liq raqam va parol hech qachon log'ga yozilmaydi.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_password
from app.models.enums import NotificationType, OtpPurpose
from app.models.otp import OtpCode
from app.models.user import User
from app.repositories.otp_repository import OtpRepository
from app.services.notification_service import NotificationService
from app.services.sms_provider import SmsDeliveryError, get_sms_provider, mask_phone

logger = logging.getLogger(__name__)

_DIGITS = "0123456789"

# Mashina kodlari — frontend shular bo'yicha matn va keyingi qadamni tanlaydi.
REAUTH_REQUIRED = "reauth_required"
PHONE_TAKEN = "phone_taken"
SMS_SEND_FAILED = "sms_send_failed"
PHONE_CHANGE_REQUIRES_VERIFICATION = "phone_change_requires_verification"


def _hash_code(code: str) -> str:
    """Kodni HMAC-SHA256 bilan hash qiladi (kalit — settings.secret_key).

    HMAC (oddiy sha256 emas): kalitsiz hujumchi lug'at (rainbow table) bilan
    6 xonali kodni oldindan hisoblab qo'ya olmasligi uchun.
    """
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        code.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _generate_code(length: int) -> str:
    """`length` xonali tasodifiy raqamli kod (yetakchi nol saqlanadi)."""
    return "".join(secrets.choice(_DIGITS) for _ in range(length))


def _too_many(detail: str, retry_after: int | None = None) -> HTTPException:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail, headers=headers
    )


class OtpService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.otps = OtpRepository(db)

    # --- Kod so'rash ---------------------------------------------------------

    def request_phone_code(
        self,
        user: User,
        phone: str,
        *,
        ip: str | None = None,
        password: str | None = None,
        auth_time: datetime | None = None,
    ) -> tuple[OtpCode, str]:
        """Akkaunt uchun `phone` ga kod yuboradi. `(OtpCode, xom kod)` qaytaradi.

        Xom kod faqat chaqiruvchiga (non-prod'da `debug_code` uchun) — DBda saqlanmaydi.
        Raqam boshqa akkauntda tasdiqlanganmi — bu yerda AYTILMAYDI (raqamlarni sinab
        ko'rish orqali kimniki ekanini bilib bo'lmasin); bu tasdiqlashda, raqam egasi
        ekanligi isbotlangandan keyin tekshiriladi.
        """
        if not settings.otp_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OTP tasdiqlash vaqtincha o'chirilgan",
            )
        if user.phone_verified_at is not None and user.phone == phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Bu raqam allaqachon tasdiqlangan"
            )
        if user.phone_verified_at is not None:
            self._require_reauth(user, password, auth_time)

        now = datetime.now(UTC)
        self._enforce_cooldown(user, phone, now)
        self._enforce_daily_limits(user, phone, ip, now)

        code = _generate_code(settings.otp_code_length)
        self.otps.expire_active_for_user(user.id, OtpPurpose.PHONE_VERIFY, now)
        otp = self.otps.add(
            OtpCode(
                user_id=user.id,
                phone=phone,
                code_hash=_hash_code(code),
                purpose=OtpPurpose.PHONE_VERIFY,
                expires_at=now + timedelta(seconds=settings.otp_ttl_seconds),
                ip=ip,
            )
        )

        minutes = settings.otp_ttl_seconds // 60
        text = f"Bazart tasdiqlash kodi: {code}. Amal qilish muddati: {minutes} daqiqa."
        try:
            result = get_sms_provider().send(phone, text)
            if not result.delivered:
                raise SmsDeliveryError("provayder xabarni qabul qilmadi")
        except SmsDeliveryError as exc:
            # Kod bekor: foydalanuvchi cooldown'siz qayta urina oladi, limit sarflanmaydi.
            self.db.rollback()
            logger.warning(
                "otp.sms_failed user_id=%s phone=%s reason=%s", user.id, mask_phone(phone), exc
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=SMS_SEND_FAILED
            ) from None
        self.db.commit()
        self.db.refresh(otp)
        logger.info("otp.sent user_id=%s phone=%s", user.id, mask_phone(phone))
        return otp, code

    # --- Kodni tekshirish --------------------------------------------------------

    def verify_phone_code(self, user: User, phone: str, code: str) -> User:
        """Kod to'g'ri bo'lsa raqam akkauntga yoziladi va tasdiqlanadi (bitta tranzaksiyada).

        Tasdiqlangan raqam almashtirilsa — eski raqam o'rniga yangisi, foydalanuvchiga
        bildirishnoma. Raqam boshqa faol akkauntda tasdiqlangan bo'lsa — 409 (DB indeksi
        poygada ham ushlaydi).
        """
        now = datetime.now(UTC)
        otp = self.otps.get_active_for_update(user.id, OtpPurpose.PHONE_VERIFY, now)
        if otp is None or otp.phone != phone:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kod topilmadi yoki muddati o'tgan",
            )
        if otp.attempts >= settings.otp_max_attempts:
            self.db.rollback()
            raise _too_many("Juda ko'p noto'g'ri urinish. Yangi kod so'rang.")

        if not hmac.compare_digest(otp.code_hash, _hash_code(code)):
            otp.attempts += 1
            locked = otp.attempts >= settings.otp_max_attempts
            self.db.commit()
            if locked:
                logger.warning("otp.locked user_id=%s phone=%s", user.id, mask_phone(phone))
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Noto'g'ri kod")

        otp.consumed_at = now
        previous = user.phone if user.phone_verified_at is not None else None
        changed = previous is not None and previous != phone
        try:
            user.phone = phone
            user.phone_verified_at = now
            # Avval raqamni yozamiz: band bo'lsa IntegrityError shu yerda (bildirishnomadan oldin).
            self.db.flush()
            if changed:
                NotificationService(self.db).create(
                    user_id=user.id,
                    type=NotificationType.PHONE_CHANGED,
                    title="Telefon raqamingiz almashtirildi",
                    body=(
                        f"Akkauntingizdagi tasdiqlangan raqam {mask_phone(phone)} ga "
                        "almashtirildi. Bu siz bo'lmasangiz, darhol parolni tiklang va "
                        "bizga yozing."
                    ),
                    payload={"phone": mask_phone(phone)},
                )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            logger.info("otp.phone_taken user_id=%s phone=%s", user.id, mask_phone(phone))
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=PHONE_TAKEN) from None
        self.db.refresh(user)
        logger.info(
            "otp.verified user_id=%s phone=%s changed=%s", user.id, mask_phone(phone), changed
        )
        return user

    # --- Yordamchilar ------------------------------------------------------------

    def _require_reauth(self, user: User, password: str | None, auth_time: datetime | None) -> None:
        """Tasdiqlangan raqamni almashtirishdan oldin: joriy parol yoki yaqinda login.

        Google orqali kirganlar parolni bilmasligi mumkin — ular uchun `auth_time`
        (sessiya boshi, access token'da) `phone_change_reauth_minutes` ichida bo'lishi kerak.
        403 (401 emas): 401 klientda jim refresh'ni ishga tushirardi, bu esa yordam bermaydi.
        """
        if password and verify_password(password, user.hashed_password):
            return
        window = timedelta(minutes=settings.phone_change_reauth_minutes)
        if auth_time is not None and datetime.now(UTC) - auth_time <= window:
            return
        logger.info("otp.reauth_required user_id=%s", user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=REAUTH_REQUIRED)

    def _enforce_cooldown(self, user: User, phone: str, now: datetime) -> None:
        """Raqamga yoki akkauntga oxirgi kod juda yaqinda yuborilgan bo'lsa — 429."""
        cooldown = settings.otp_resend_cooldown_seconds
        if cooldown <= 0:
            return
        for last in (
            self.otps.get_latest_for_phone(phone, OtpPurpose.PHONE_VERIFY),
            self.otps.get_latest_for_user(user.id, OtpPurpose.PHONE_VERIFY),
        ):
            if last is None:
                continue
            elapsed = (now - last.created_at).total_seconds()
            if elapsed < cooldown:
                retry_after = int(cooldown - elapsed) + 1
                raise _too_many(
                    f"Yangi kod so'rashdan oldin {retry_after} soniya kuting", retry_after
                )

    def _enforce_daily_limits(self, user: User, phone: str, ip: str | None, now: datetime) -> None:
        """Kuniga bir raqam, bir akkaunt va bir IP uchun kodlar sonini cheklaydi (SMS narxi)."""
        day_ago = now - timedelta(days=1)
        if self.otps.count_since_for_phone(phone, day_ago) >= settings.otp_daily_limit_per_phone:
            raise _too_many("Bu raqam uchun kunlik kod limiti tugadi")
        if self.otps.count_since_for_user(user.id, day_ago) >= settings.otp_daily_limit_per_user:
            raise _too_many("Akkaunt uchun kunlik kod limiti tugadi")
        if ip is not None and (
            self.otps.count_since_for_ip(ip, day_ago) >= settings.otp_daily_limit_per_ip
        ):
            raise _too_many("Bu IP uchun kunlik kod limiti tugadi")
