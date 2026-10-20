"""Celery ilovasi — fon vazifalari uchun (broker/backend: Redis).

Vazifalar:
  * Davriy (beat): muddati o'tgan auksionlarni yopish, takliflar muddati, eslatmalar.
    Ilgari bu `main.py` lifespan'idagi in-process asyncio loop edi; prod'da
    Celery beat ishonchli, ko'p-instans muhitida bir marta bajaradi.
  * Navbatli (queue): push bildirishnoma va email yuborish — so'rov oqimidan
    chiqarib, foydalanuvchini kutdirmaydi.

Worker:  celery -A app.core.celery_app worker -l info
Beat:    celery -A app.core.celery_app beat -l info
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import schedule

from app.core.config import settings

celery_app = Celery(
    "bazart",
    broker=settings.effective_celery_broker,
    backend=settings.effective_celery_backend,
    include=[
        "app.tasks.scheduled",
        "app.tasks.notifications",
        "app.tasks.email",
    ],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_eager,
    task_eager_propagates=True,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    broker_connection_retry_on_startup=True,
)


def build_beat_schedule() -> dict:
    """Davriy vazifalar jadvali (testda ham shu funksiya tekshiriladi)."""
    return {
        "close-due-auctions": {
            "task": "app.tasks.scheduled.close_due_auctions_task",
            "schedule": schedule(settings.auction_closer_interval_seconds),
        },
        "auto-confirm-deals": {
            "task": "app.tasks.scheduled.auto_confirm_deals_task",
            "schedule": schedule(settings.deal_auto_confirm_interval_seconds),
        },
        "expire-next-offers": {
            "task": "app.tasks.scheduled.expire_next_offers_task",
            "schedule": schedule(settings.next_offer_expiry_interval_seconds),
        },
        "notify-ending-soon": {
            "task": "app.tasks.scheduled.notify_ending_soon_task",
            "schedule": schedule(settings.ending_soon_interval_seconds),
        },
        "price-drop-alerts": {
            "task": "app.tasks.scheduled.price_drop_alerts_task",
            "schedule": schedule(settings.price_drop_interval_seconds),
        },
        "expire-offers": {
            "task": "app.tasks.scheduled.expire_offers_task",
            "schedule": schedule(settings.offer_expiry_interval_seconds),
        },
    }


# Davriy vazifalar — faqat beat yoqilganda ro'yxatga olinadi (aks holda bo'sh).
if settings.celery_beat_enabled:
    celery_app.conf.beat_schedule = build_beat_schedule()
