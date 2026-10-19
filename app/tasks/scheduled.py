"""Davriy (Celery beat) vazifalar: auksion yopish va auto-complete.

Yopish/capture mantig'i o'zgarmaydi — mavjud toza funksiyalar
(`close_due_auctions`, `auto_complete_due_orders`) qayta ishlatiladi. Bu yerda
faqat "Celery kontekstida yangi DB sessiya ochib chaqirish" bor.
"""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.auction_closer import close_due_auctions
from app.services.auto_complete import auto_complete_due_orders
from app.services.ending_soon import notify_ending_soon
from app.services.offer_service import OfferService
from app.services.price_alerts import notify_price_drops

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.scheduled.close_due_auctions_task")
def close_due_auctions_task() -> int:
    """Muddati o'tgan faol auksionlarni yopadi. Yopilganlar sonini qaytaradi."""
    db = SessionLocal()
    try:
        closed = close_due_auctions(db)
        if closed:
            logger.info("Celery: %s ta auksion yopildi", closed)
        return closed
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduled.auto_complete_orders_task")
def auto_complete_orders_task() -> int:
    """Muddati o'tgan hold'larni capture qiladi. Yakunlanganlar sonini qaytaradi."""
    db = SessionLocal()
    try:
        done = auto_complete_due_orders(db)
        if done:
            logger.info("Celery: %s ta order avtomatik yakunlandi", done)
        return done
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduled.notify_ending_soon_task")
def notify_ending_soon_task() -> int:
    """Tugashiga oz qolgan auksionlar bo'yicha eslatma. Eslatilganlar sonini qaytaradi."""
    db = SessionLocal()
    try:
        notified = notify_ending_soon(db)
        if notified:
            logger.info("Celery: %s ta auksion bo'yicha ENDING_SOON yuborildi", notified)
        return notified
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduled.expire_offers_task")
def expire_offers_task() -> int:
    """Muddati o'tgan takliflar va taklifli e'lonlarni yopadi. Yopilganlar soni."""
    db = SessionLocal()
    try:
        offers, listings = OfferService(db).expire_due()
        if offers or listings:
            logger.info("Celery: %s ta taklif, %s ta e'lon muddati yopildi", offers, listings)
        return offers + listings
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduled.price_drop_alerts_task")
def price_drop_alerts_task() -> int:
    """Pasayuvchi auksionlarda "narx tushdi" xabari. Xabarlangan auksionlar soni."""
    db = SessionLocal()
    try:
        notified = notify_price_drops(db)
        if notified:
            logger.info("Celery: %s ta auksion bo'yicha PRICE_DROPPED yuborildi", notified)
        return notified
    finally:
        db.close()
