"""Ishonch signallari va bekor qilish cheklovi (Faza E2.9, docs/DEALS.md §8).

Escrow yo'q — xaridor va sotuvchi bir-biriga faqat ochiq signallar orqali ishonadi: tugallangan
kelishuvlar va AYBDOR sifatida bekor qilinganlar. Hisoblagichlar saqlanmaydi, kelishuvlardan
hisoblanadi: alohida ustun kelishuv holati bilan ajralib qolishi (drift) mumkin edi.

Cheklov: `deal_cancel_window_days` ichida `deal_cancel_limit` ta aybli bekor qilish ->
oxirgisidan `deal_cancel_ban_days` kun bid, taklif va buy-now taqiqi. Yutib olib javob bermaslik
(yoki sotib, keyin rad etish) bepul bo'lmasin.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.deal import Deal
from app.models.enums import DealStatus
from app.models.user import User

TRADING_RESTRICTED = "trading_restricted"


@dataclass(frozen=True)
class UserStats:
    deals_completed: int
    cancelled_as_buyer: int
    cancelled_as_seller: int


class TrustService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def stats(self, user_id: int) -> UserStats:
        """Profil hisoblagichlari. Bekor qilishlar faqat AYBDOR tomonga yoziladi."""
        completed = self.db.scalar(
            select(func.count(Deal.id)).where(
                Deal.status == DealStatus.COMPLETED,
                (Deal.buyer_id == user_id) | (Deal.seller_id == user_id),
            )
        )
        at_fault = (Deal.status == DealStatus.CANCELLED) & (Deal.at_fault_id == user_id)
        as_buyer = self.db.scalar(
            select(func.count(Deal.id)).where(at_fault, Deal.buyer_id == user_id)
        )
        as_seller = self.db.scalar(
            select(func.count(Deal.id)).where(at_fault, Deal.seller_id == user_id)
        )
        return UserStats(
            deals_completed=completed or 0,
            cancelled_as_buyer=as_buyer or 0,
            cancelled_as_seller=as_seller or 0,
        )

    def restricted_until(self, user_id: int, now: datetime | None = None) -> datetime | None:
        """Faol taqiq tugash vaqti yoki None.

        Har aybli bekor qilish t_i uchun: undan oldingi (limit-1) tasi bilan birga oyna
        ichida bo'lsa, taqiq t_i + ban_days gacha. Faqat oxirgi (oyna + taqiq) davr o'qiladi.
        """
        now = now or datetime.now(UTC)
        window = timedelta(days=settings.deal_cancel_window_days)
        ban = timedelta(days=settings.deal_cancel_ban_days)
        limit = settings.deal_cancel_limit
        times = [
            t if t.tzinfo else t.replace(tzinfo=UTC)
            for t in self.db.scalars(
                select(Deal.cancelled_at)
                .where(
                    Deal.status == DealStatus.CANCELLED,
                    Deal.at_fault_id == user_id,
                    Deal.cancelled_at >= now - window - ban,
                )
                .order_by(Deal.cancelled_at)
            )
        ]
        until: datetime | None = None
        for i in range(limit - 1, len(times)):
            if times[i] - times[i - limit + 1] <= window:
                candidate = times[i] + ban
                if candidate > now and (until is None or candidate > until):
                    until = candidate
        return until

    def ensure_can_trade(self, user: User) -> None:
        """Bid, taklif va buy-now oldidan. Taqiq faol bo'lsa 403 `trading_restricted`."""
        if self.restricted_until(user.id) is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=TRADING_RESTRICTED)
