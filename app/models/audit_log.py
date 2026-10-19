from datetime import UTC, datetime

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Pul harakatlarining o'zgarmas jurnali (INSERT only).

    Nizoda ("men to'lamadim" / "men jo'natdim") yagona ishonchli dalil.
    Loglar aylanadi va o'chadi — bu jadval o'chmaydi.

    QOIDA: faqat INSERT. UPDATE/DELETE TAQIQ (prod'da REVOKE bilan
    mustahkamlanadi). Shu sababli `updated_at` yo'q — yozuv o'zgarmaydi.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # actor_id nullable: worker/webhook tomonidan qilingan operatsiyalar uchun.
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)  # PAYMENT_HELD, ...
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)  # auction, deal, user
    entity_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
