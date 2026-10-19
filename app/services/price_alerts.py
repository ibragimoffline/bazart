"""Pasayuvchi auksionda "Narx tushdi" xabari kuzatuvchilarga.

Narx bazada saqlanmaydi (vaqtdan hisoblanadi), shuning uchun "pasayish hodisasi" ham
yo'q — fon vazifasi har tik'da joriy narxni hisoblab, oxirgi xabardagi narx bilan
solishtiradi. Har soatlik pasayishda xabar yuborish spam bo'lardi; shuning uchun xabar:
  - oxirgi xabardagi (yoki boshlang'ich) narxdan kamida `price_drop_notify_min_bps`
    (default 10%) pasaygach, YOKI
  - narx pastki chegaraga yetganda (oxirgi imkoniyat) — bir marta.
`auctions.last_price_alert` — oxirgi xabar narxi (takrorlanmaslik).

Har auksion alohida tranzaksiyada `FOR UPDATE SKIP LOCKED` bilan: xarid qilinayotgan
(qulflangan) auksion kutilmaydi — keyingi tik'da olinadi; parallel worker'lar bir
auksionni ikki marta xabarlamaydi.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auction import Auction
from app.models.enums import AuctionStatus, NotificationType, PricingMode
from app.money import dropped_by_at_least, format_soum_text
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.notification_service import NotificationService
from app.services.price_schedule import descending_price_at

logger = logging.getLogger(__name__)


def notify_price_drops(db: Session) -> int:
    """Narxi sezilarli tushgan pasayuvchi auksionlar bo'yicha xabar. Xabarlangan auksionlar soni."""
    candidate_ids = list(
        db.scalars(
            select(Auction.id).where(
                Auction.status == AuctionStatus.ACTIVE,
                Auction.pricing_mode == PricingMode.DESCENDING,
                Auction.winner_id.is_(None),
            )
        )
    )
    notified = 0
    for auction_id in candidate_ids:
        try:
            if _check_auction(db, auction_id):
                notified += 1
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("PRICE_DROPPED: auksion=%s xabarini yuborib bo'lmadi", auction_id)
    return notified


def _check_auction(db: Session, auction_id: int) -> bool:
    auction = db.scalars(
        select(Auction).where(Auction.id == auction_id).with_for_update(skip_locked=True)
    ).one_or_none()
    if (
        auction is None
        or auction.status != AuctionStatus.ACTIVE
        or auction.winner_id is not None
        or auction.price_decrement is None
        or auction.price_drop_interval_minutes is None
        or auction.reserve_price is None
    ):
        return False

    now = datetime.now(UTC)
    price = descending_price_at(
        starting_price=auction.starting_price,
        price_decrement=auction.price_decrement,
        interval_minutes=auction.price_drop_interval_minutes,
        floor_price=auction.reserve_price,
        start_time=auction.start_time,
        at=now,
    )
    baseline = auction.last_price_alert or auction.starting_price
    at_floor = price <= auction.reserve_price
    if price >= baseline:
        return False
    if not (at_floor or dropped_by_at_least(baseline, price, settings.price_drop_notify_min_bps)):
        return False

    auction.last_price_alert = price
    db.add(auction)

    recipients = set(WatchlistRepository(db).list_user_ids_for_auction(auction.id))
    recipients.discard(auction.seller_id)
    title_text = auction.item.title if auction.item else "Lot"
    body = (
        f"«{title_text}»: narx {format_soum_text(baseline)} → {format_soum_text(price)} soʻm."
        + (" Bu eng past narx — boshqa tushmaydi." if at_floor else " Birinchi xaridor oladi.")
    )
    notifier = NotificationService(db)
    for user_id in sorted(recipients):
        notifier.create(
            user_id=user_id,
            type=NotificationType.PRICE_DROPPED,
            title="Narx tushdi",
            body=body,
            payload={
                "auction_id": auction.id,
                "previous_price": str(baseline),
                "current_price": str(price),
                "at_floor": at_floor,
            },
        )
    logger.info(
        "PRICE_DROPPED: auksion=%s %s -> %s, %s ta kuzatuvchi",
        auction.id,
        baseline,
        price,
        len(recipients),
    )
    return True
