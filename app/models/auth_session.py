import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthSession(Base):
    """Refresh-sessiya: bitta kirish (login / Google) = bitta qator.

    Refresh token har ishlatilganda almashtiriladi (rotation). Qatorda faqat token
    identifikatorlari (`jti`) saqlanadi, token o'zi EMAS — baza sizib chiqsa ham undan
    sessiyani tiklab bo'lmaydi.

    `previous_jti` + `rotated_at` — parallel so'rovlar uchun qisqa "grace" oynasi: ikki
    tab bir vaqtda eski cookie bilan kelsa, ikkinchisi sessiyani bekor qilmaydi. Oynadan
    tashqarida eski token qayta kelsa — bu o'g'irlangan token belgisi, butun sessiya
    bekor qilinadi (replay detection).
    """

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    current_jti: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    # Sirpanuvchi muddat: har rotation'da now + refresh_token_expire_days.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # "logout" | "reuse" | "password_reset" — audit uchun.
    revoke_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
