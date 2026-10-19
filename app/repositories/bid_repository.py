from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.bid import Bid
from app.models.enums import BidStatus

# Bekor qilingan holatlar — joriy narx/g'olib hisobiga kirmaydi.
_DEAD_STATUSES = (BidStatus.RETRACTED, BidStatus.INVALIDATED, BidStatus.CANCELLED)


class BidRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, bid: Bid) -> Bid:
        self.db.add(bid)
        self.db.commit()
        self.db.refresh(bid)
        return bid

    def get(self, bid_id: int) -> Bid | None:
        return self.db.get(Bid, bid_id)

    def list_for_auction(self, auction_id: int, *, limit: int = 50) -> list[Bid]:
        """Auksion bid tarixi (yangi -> eski). Bidder bitta so'rovda yuklanadi —
        BidRead ismni maskalash uchun `bid.bidder` ga murojaat qiladi."""
        statement = (
            select(Bid)
            .options(selectinload(Bid.bidder))
            .where(Bid.auction_id == auction_id)
            .order_by(Bid.created_at.desc(), Bid.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def get_highest_valid_bid(self, auction_id: int) -> Bid | None:
        statement = (
            select(Bid)
            .where(Bid.auction_id == auction_id, Bid.status == BidStatus.VALID)
            .order_by(Bid.amount.desc(), Bid.created_at.asc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_highest_live_bid_excluding(
        self, auction_id: int, exclude_bidder_ids: set[int]
    ) -> Bid | None:
        """Eng yuqori tirik bid (VALID/OUTBID) — berilgan bidderlarnikidan tashqari.

        Keyingi bidderga taklif (E2.10) uchun: sotuvchi, bekor qilingan kelishuv xaridorlari
        va oldin taklif olganlar chiqarib tashlanadi — bid tarixi O'ZGARMAYDI. Teng summada
        erta qo'yilgani ustun.
        """
        statement = (
            select(Bid)
            .where(
                Bid.auction_id == auction_id,
                Bid.status.in_([BidStatus.VALID, BidStatus.OUTBID]),
                Bid.bidder_id.not_in(exclude_bidder_ids or {-1}),
            )
            .order_by(Bid.amount.desc(), Bid.created_at.asc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_highest_active_bid(self, auction_id: int) -> Bid | None:
        """Eng yuqori TIRIK bid (VALID yoki OUTBID — RETRACTED/INVALIDATED emas).

        Retraction/invalidation'dan keyin narxni qayta hisoblashda kerak: yetakchi
        bid o'chirilsa, undan keyingi (OUTBID) bid qayta tiklanishi lozim —
        get_highest_valid_bid faqat VALID'ni ko'radi va uni topa olmasdi.
        """
        statement = (
            select(Bid)
            .where(Bid.auction_id == auction_id, Bid.status.not_in(_DEAD_STATUSES))
            .order_by(Bid.amount.desc(), Bid.created_at.asc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_by_idempotency_key(self, bidder_id: int, key: str) -> Bid | None:
        """Idempotentlik: shu bidder shu kalit bilan yozgan bidni qaytaradi."""
        statement = select(Bid).where(Bid.bidder_id == bidder_id, Bid.idempotency_key == key)
        return self.db.scalar(statement)

    def count_bids(self, auction_id: int) -> int:
        """Auksiondagi bidlar soni (bekor qilinganlar/proksi hisobga olinmaydi)."""
        statement = select(func.count(Bid.id)).where(
            Bid.auction_id == auction_id,
            Bid.is_proxy.is_(False),
            Bid.status.not_in(_DEAD_STATUSES),
        )
        return self.db.scalar(statement) or 0

    def list_bidder_ids(self, auction_id: int) -> list[int]:
        """Auksionda tirik bidi bor foydalanuvchilar (bekor qilinganlar tashqarida)."""
        statement = (
            select(Bid.bidder_id)
            .distinct()
            .where(
                Bid.auction_id == auction_id,
                Bid.status.not_in(_DEAD_STATUSES),
            )
        )
        return list(self.db.scalars(statement))

    def count_distinct_bidders(self, auction_id: int) -> int:
        """Auksiondagi noyob bidderlar soni (bekor qilinganlar/proksi tashqarida)."""
        statement = select(func.count(func.distinct(Bid.bidder_id))).where(
            Bid.auction_id == auction_id,
            Bid.is_proxy.is_(False),
            Bid.status.not_in(_DEAD_STATUSES),
        )
        return self.db.scalar(statement) or 0
