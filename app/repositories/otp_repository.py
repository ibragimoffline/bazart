from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.enums import OtpPurpose
from app.models.otp import OtpCode


class OtpRepository:
    """OTP kodlar jadvaliga kirish — faqat DB o'qish/yozish. Commit — xizmatda."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, otp: OtpCode) -> OtpCode:
        """Yangi kod — faqat flush (SMS yuborilmasa xizmat rollback qiladi)."""
        self.db.add(otp)
        self.db.flush()
        return otp

    def get_latest_for_phone(self, phone: str, purpose: OtpPurpose) -> OtpCode | None:
        """Raqamga yuborilgan eng oxirgi kod (holatidan qat'i nazar) — resend cooldown uchun."""
        statement = (
            select(OtpCode)
            .where(OtpCode.phone == phone, OtpCode.purpose == purpose)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_latest_for_user(self, user_id: int, purpose: OtpPurpose) -> OtpCode | None:
        """Akkaunt so'ragan eng oxirgi kod — raqamni almashtirib cooldown'ni chetlab o'tmasin."""
        statement = (
            select(OtpCode)
            .where(OtpCode.user_id == user_id, OtpCode.purpose == purpose)
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_active_for_update(
        self, user_id: int, purpose: OtpPurpose, now: datetime
    ) -> OtpCode | None:
        """Akkauntning faol (ishlatilmagan, muddati o'tmagan) kodi — QULF ostida.

        `FOR UPDATE`: ikki parallel tekshiruv navbat bilan ko'riladi. Ikkinchisi qulfni
        olgach qatorni qayta baholaydi (READ COMMITTED) — `consumed_at` endi to'lgan, kod
        topilmaydi. Shu bilan bir kod ikki marta ishlatilmaydi va urinishlar soni yo'qolmaydi.
        Yangi kod berilganda eskilari bekor qilinadi, shuning uchun faol kod ko'pi bilan bitta.
        """
        statement = (
            select(OtpCode)
            .where(
                OtpCode.user_id == user_id,
                OtpCode.purpose == purpose,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > now,
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        return self.db.scalar(statement)

    def expire_active_for_user(self, user_id: int, purpose: OtpPurpose, now: datetime) -> None:
        """Akkauntning hali faol kodlarini darhol eskirtiradi (yangi kod berilganda)."""
        self.db.execute(
            update(OtpCode)
            .where(
                OtpCode.user_id == user_id,
                OtpCode.purpose == purpose,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > now,
            )
            .values(expires_at=now)
        )

    def count_since_for_phone(self, phone: str, since: datetime) -> int:
        """`since` dan beri shu raqamga yaratilgan kodlar soni (kunlik limit uchun)."""
        statement = (
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.phone == phone, OtpCode.created_at >= since)
        )
        return self.db.scalar(statement) or 0

    def count_since_for_ip(self, ip: str, since: datetime) -> int:
        """`since` dan beri shu IP'dan yaratilgan kodlar soni (kunlik limit uchun)."""
        statement = (
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.ip == ip, OtpCode.created_at >= since)
        )
        return self.db.scalar(statement) or 0

    def count_since_for_user(self, user_id: int, since: datetime) -> int:
        """`since` dan beri shu akkaunt so'ragan kodlar soni (kunlik limit uchun)."""
        statement = (
            select(func.count())
            .select_from(OtpCode)
            .where(OtpCode.user_id == user_id, OtpCode.created_at >= since)
        )
        return self.db.scalar(statement) or 0
