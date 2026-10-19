from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.webhook import is_fresh
from app.repositories.webhook_repository import WebhookRepository


class WebhookService:
    """To'lov provayderi webhook hodisalarini replay va dedup himoyasi bilan qabul qiladi.

    Faza E: savdo to'lovi yo'q, shuning uchun hodisa hech qanday to'lov holatiga ulanmaydi.
    Himoya qatlami hamyon to'ldirish (E5) uchun saqlanadi.

    Ikki qatlamli himoya:
      1. Replay — hodisa vaqti juda eski bo'lsa (`is_fresh` False), rad etamiz.
         Imzo to'g'ri bo'lsa ham, eski (haqiqiy) webhook'ni qayta yuborish
         orqali hujum qilib bo'lmasligi uchun.
      2. Dedup — `(provider, event_id)` allaqachon yozilgan bo'lsa, hodisa
         qayta ishlanmaydi (idempotent). PSP bir xil hodisani bir necha marta
         yuborishi mumkin.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = WebhookRepository(db)

    def process(
        self,
        *,
        provider: str,
        event_id: str,
        timestamp: int,
        payload: dict,
    ) -> str:
        """Hodisani qayd etadi. Natija: "processed" / "duplicate" / "stale"."""
        now_ts = int(datetime.now(UTC).timestamp())
        if not is_fresh(timestamp, now_ts):
            return "stale"

        if self.repo.exists(provider, event_id):
            return "duplicate"

        event = self.repo.create(provider, event_id, payload)
        self.repo.mark_processed(event)
        self.db.commit()
        return "processed"
