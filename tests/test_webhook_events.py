"""Webhook replay + dedup himoyasi (`WebhookService`) uchun integratsiya testlari.

Faza E: savdo to'lovi endpointi olib tashlandi. Himoya qatlami hamyon to'ldirish
webhook'i (E5) uchun saqlanadi, shuning uchun servis to'g'ridan-to'g'ri sinaladi.
"""

import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent
from app.services.webhook_service import WebhookService


def _now_ts() -> int:
    return int(datetime.datetime.now(datetime.UTC).timestamp())


def _event_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(WebhookEvent)) or 0


def _process(db: Session, event_id: str, timestamp: int) -> str:
    return WebhookService(db).process(
        provider="psp", event_id=event_id, timestamp=timestamp, payload={"type": "topup"}
    )


def test_webhook_new_event_processed(db_session: Session) -> None:
    assert _process(db_session, "evt_1", _now_ts()) == "processed"
    assert _event_count(db_session) == 1

    event = db_session.scalar(select(WebhookEvent).where(WebhookEvent.event_id == "evt_1"))
    assert event is not None
    assert event.provider == "psp"
    assert event.processed_at is not None


def test_webhook_duplicate_event_deduped(db_session: Session) -> None:
    assert _process(db_session, "evt_dup", _now_ts()) == "processed"
    # Aynan o'sha event_id ikkinchi marta — DB'da hali BITTA.
    assert _process(db_session, "evt_dup", _now_ts()) == "duplicate"
    assert _event_count(db_session) == 1


def test_webhook_stale_event_rejected(db_session: Session) -> None:
    assert _process(db_session, "evt_old", _now_ts() - 1000) == "stale"
    # Stale hodisa yozilmaydi.
    assert _event_count(db_session) == 0
