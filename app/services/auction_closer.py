"""Auksionni avtomatik yopuvchi fon vazifasi (closer worker).

Ilgari auksion faqat sotuvchi qo'lda `POST /auctions/{id}/close` chaqirsa
yopilardi. Bu manfaatlar to'qnashuvi: agar natija sotuvchiga yoqmasa
(masalan narx past yoki reserve bajarilmagan), u auksionni umuman
yopmasligi mumkin edi — g'olib esa lotni kuta-kuta qoladi.

Yechim: `end_time` o'tgan har bir ACTIVE auksionni fon vazifasi
avtomatik yopadi. Yopish mantig'i (g'olib aniqlash, deal yaratish,
FOR UPDATE qulf, state machine) `AuctionService.close_auction` da —
bu modul faqat "muddati o'tganlarni top va yop" orkestratsiyasini qiladi.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auction import Auction
from app.models.enums import AuctionStatus
from app.services.auction_service import AuctionService
from app.services.ending_soon import notify_ending_soon
from app.services.offer_service import OfferService
from app.services.price_alerts import notify_price_drops

logger = logging.getLogger(__name__)


def activate_due_auctions(db: Session) -> int:
    """Boshlanish vaqti kelgan SCHEDULED auksionlarni ACTIVE qiladi (faollashganlar soni).

    Ilgari rejalashtirilgan auksion faqat birinchi bid'da "dangasa" faollashardi:
    katalogda ko'rinmasdi, buy-now (pasayuvchi auksionda yagona yo'l) uni rad etardi va
    closer faqat ACTIVE'ni yopgani uchun bunday auksion hech qachon yopilmasdi.
    Har auksion qulf ostida (`AuctionService.activate_if_started`), alohida tranzaksiyada.
    """
    now = datetime.now(UTC)
    due_ids = (
        db.execute(
            select(Auction.id)
            .where(Auction.status == AuctionStatus.SCHEDULED)
            .where(Auction.start_time <= now)
        )
        .scalars()
        .all()
    )
    activated = 0
    for auction_id in due_ids:
        try:
            if AuctionService(db).activate_if_started(auction_id):
                activated += 1
        except Exception:
            logger.warning("Auksion %s ni faollashtirish muvaffaqiyatsiz", auction_id)
    return activated


def close_due_auctions(db: Session) -> int:
    """Muddati o'tgan faol auksionlarni yopadi, yopilganlar sonini qaytaradi.

    Toza, fon loop'siz funksiya — to'g'ridan-to'g'ri testlanadi.

    `end_time <= now` va status ACTIVE bo'lgan auksionlar tanlanadi.
    Anti-sniping `end_time` ni kelajakka surgan bo'lsa, u shu shart
    bilan avtomatik chetlab o'tiladi (hali "muddati o'tgan" hisoblanmaydi).

    Har bir yopish `try/except` bilan o'raladi: worker HTTP kontekstida
    emas, shuning uchun poyga (parallel bid/close auksionni allaqachon
    ENDED qilib qo'ygan) `HTTPException` ko'tarsa ham butun loop
    to'xtamasligi kerak — xatoni log qilib keyingisiga o'tamiz.
    """
    # Avval vaqti kelgan rejalashtirilganlarni faollashtiramiz — muddati ham o'tgan
    # bo'lsa, ular shu tik'da yopiladi.
    activate_due_auctions(db)
    now = datetime.now(UTC)
    due_ids = (
        db.execute(
            select(Auction.id)
            .where(Auction.status == AuctionStatus.ACTIVE)
            .where(Auction.end_time <= now)
        )
        .scalars()
        .all()
    )

    closed = 0
    for auction_id in due_ids:
        try:
            AuctionService(db).close_auction(auction_id)
            closed += 1
        except Exception:
            # Poyga yoki allaqachon yopilgan holat — kutilgan, o'tkazamiz.
            logger.warning("Auksion %s ni avtomatik yopish muvaffaqiyatsiz", auction_id)

    return closed


async def _closer_loop() -> None:
    """Davriy ravishda muddati o'tgan auksionlarni yopib turuvchi loop.

    Har tik'da YANGI sync sessiya ochiladi (uzoq yashovchi sessiya
    eskirgan ma'lumot ushlab qolmasin) va sync DB ishi `to_thread`
    orqali bajariladi — event loop bloklanmaydi.
    """
    interval = settings.auction_closer_interval_seconds
    logger.info("Auksion closer worker ishga tushdi (interval=%ss)", interval)
    while True:
        try:
            await asyncio.to_thread(_run_once)
        except Exception:
            logger.exception("Auksion closer tik'ida kutilmagan xato")
        await asyncio.sleep(interval)


def _run_once() -> None:
    """Bitta tik: sessiya ochib, muddati o'tganlarni yopadi va eslatmalarni yuboradi."""
    db = SessionLocal()
    try:
        closed = close_due_auctions(db)
        if closed:
            logger.info("Auksion closer %s ta auksionni yopdi", closed)
        # Eslatma xatosi yopishni to'xtatmasin — alohida himoyalangan.
        try:
            notify_ending_soon(db)
        except Exception:
            logger.exception("ENDING_SOON eslatmasini yuborishda xato")
        try:
            OfferService(db).expire_due()
        except Exception:
            logger.exception("Takliflar muddatini yopishda xato")
        try:
            notify_price_drops(db)
        except Exception:
            logger.exception("PRICE_DROPPED xabarlarida xato")
    finally:
        db.close()


def start_auction_closer() -> asyncio.Task | None:
    """Closer worker'ni ishga tushiradi (yoqilgan va test bo'lmasa).

    Testlarda ishga tushirilmaydi: fon vazifasi test bazasini yoki
    boshqa testlarning auksionlarini kutilmaganda o'zgartirib qo'ymasin.
    Qaytarilgan Task shutdown'da bekor qilinishi kerak.
    """
    if not settings.auction_closer_enabled or settings.environment == "test":
        return None
    return asyncio.create_task(_closer_loop())


async def stop_auction_closer(task: asyncio.Task | None) -> None:
    """Closer worker'ni to'xtatadi (shutdown'da chaqiriladi)."""
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
