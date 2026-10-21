from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import OtpPurpose


class OtpCode(Base):
    """Telefon raqam tasdiqlash uchun bir martalik kod (OTP).

    Xom kod HECH QACHON saqlanmaydi — faqat HMAC hash (`code_hash`). Shu sababli
    bazaga kirish huquqi bo'lgan odam ham amaldagi kodni tiklay olmaydi.

    Bir raqamga bir maqsad (`purpose`) uchun ketma-ket kodlar yozilaveradi;
    tekshiruvda eng oxirgi, muddati o'tmagan va iste'mol qilinmagan kod olinadi.
    `attempts` — noto'g'ri urinishlar soni; limitdan oshsa kod bloklanadi
    (brute-force himoyasi).
    """

    __tablename__ = "otp_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    phone: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    # Kod so'ragan foydalanuvchi: kodni faqat shu akkaunt tasdiqlay oladi (boshqa akkaunt
    # birovning kodi bilan raqamni o'ziga yoza olmasin). Eski yozuvlarda NULL.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # HMAC-SHA256 hex digest (settings.secret_key kaliti bilan). Xom kod EMAS.
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(
        SqlEnum(OtpPurpose, name="otp_purpose"),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Kod muvaffaqiyatli ishlatilgan vaqt (None = hali ishlatilmagan/faol).
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # So'rov kelgan IP — kunlik IP limiti va audit uchun (ixtiyoriy).
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
