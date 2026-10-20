"""Davriy (Celery beat) vazifalar: auksion yopish, takliflar muddati, eslatmalar.

Mantiq o'zgarmaydi — mavjud toza funksiyalar (`close_due_auctions` va h.k.)
qayta ishlatiladi. Bu yerda
faqat "Celery kontekstida yangi DB sessiya ochib chaqirish" bor.
"""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.auction_closer import close_due_auctions
from app.services.auction_service import AuctionService
from app.services.deal_service import DealService
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


@celery_app.task(name="app.tasks.scheduled.auto_confirm_deals_task")
def auto_confirm_deals_task() -> int:
    """72 soatlik avto-tasdiq (docs/DEALS.md §5). Yakunlangan kelishuvlar soni."""
    db = SessionLocal()
    try:
        done = DealService(db).auto_confirm_due()
        if done:
            logger.info("Celery: %s ta kelishuv avtomatik tasdiqlandi", done)
        return done
    finally:
        db.close()


@celery_app.task(name="app.tasks.scheduled.expire_next_offers_task")
def expire_next_offers_task() -> int:
    """Keyingi bidderga takliflar muddati (E2.10). Qayd etilganlar soni."""
    db = SessionLocal()
    try:
        expired = AuctionService(db).expire_next_offers()
        if expired:
            logger.info("Celery: %s ta keyingi-bidder taklifi muddati o'tdi", expired)
        return expired
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
