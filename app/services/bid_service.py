import logging
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auction import Auction
from app.models.auction_extension import AuctionExtension
from app.models.bid import Bid
from app.models.enums import (
    AuctionStatus,
    BidStatus,
    ItemStatus,
    NotificationType,
    PricingMode,
    is_admin,
)
from app.models.user import User
from app.money import format_soum_text
from app.realtime import manager
from app.repositories.auction_repository import AuctionRepository
from app.repositories.bid_repository import BidRepository
from app.schemas.bid import BidCreate
from app.services.auction_state import assert_transition
from app.services.bid_increment import effective_min_increment
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

# Xato stavka (typo) ogohlantirishi shu koeffitsientdan oshsa beriladi:
# joriy narxdan N barobar katta bid — ehtimol nol ortiqcha terilgan.
TYPO_WARNING_MULTIPLIER = 3

# Retraction/invalidation'da faqat shu holatdagi bid o'zgartiriladi.
_RETRACTABLE_STATUSES = (BidStatus.VALID, BidStatus.OUTBID)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class BidService:
    """Bid qo'yish, qaytarib olish (retraction) va bekor qilish oqimi.

    Proxy/max-bid uchun kengaytirish nuqtasi shu yerda.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.auctions = AuctionRepository(db)
        self.bids = BidRepository(db)

    def place_bid(
        self,
        auction_id: int,
        bidder: User,
        payload: BidCreate,
        ip: str | None = None,
        device_id: str | None = None,
        user_agent: str | None = None,
        idempotency_key: str | None = None,
    ) -> Bid:
        """Bid qo'yadi. ATOMIK — race condition'siz.

        Butun mantiq BITTA tranzaksiyada:
          1) auksion qatorini FOR UPDATE bilan qulflab qayta o'qiydi
          2) validatsiya (qulf ostida — o'qilgan narx eskirmaydi)
          3) yozish + denormalizatsiya (bid_count, unique_bidder_count)
          4) bitta commit

        Qulf o'rnatilgach commit qilinmaydi: har commit qulfni bo'shatadi
        va "o'qi -> tekshir -> yoz" oynasi yana ochilib qoladi. Aynan shu
        sababli auksionni aktivlashtirish ham bu yerda commit'siz
        bajariladi (_activate_if_started_locked).

        IDEMPOTENTLIK: `idempotency_key` berilsa va shu bidder shu kalit
        bilan allaqachon bid yozgan bo'lsa — yangi bid yaratilmaydi, mavjudi
        qaytariladi (tarmoq qayta urinishi ikki marta bid qo'ymasin).

        PROXY BIDDING (orqaga mos):
          - max_amount berilmasa — oddiy bid: ko'ringan narx = amount.
          - max_amount berilsa — keyingi raqib kelganda tizim leader nomidan
            avtomatik bir qadam yuqoriga ko'taradi (leader max'igacha).
        high_bidder_max HECH QACHON javobda oshkor bo'lmaydi.
        """
        # Idempotentlik: qulfdan OLDIN tekshiramiz — takroriy so'rov bo'lsa
        # butun tranzaksiyani ochmaymiz.
        if idempotency_key:
            existing = self.bids.get_by_idempotency_key(bidder.id, idempotency_key)
            if existing is not None:
                return existing

        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )

            self._activate_if_started_locked(auction)
            self._validate_bid(auction, bidder, payload)

            # Typo ogohlantirishi joriy narx O'ZGARISHIDAN oldin hisoblanadi.
            price_before = auction.current_price

            returned_bid = self._resolve_bid(auction, bidder, payload)
            # Anti-fraud/audit izlari — chaqiruvchining bid yozuviga (proxy'ga emas).
            returned_bid.ip = ip
            returned_bid.device_id = device_id
            returned_bid.user_agent = user_agent
            returned_bid.idempotency_key = idempotency_key

            # Bid id'sini olish uchun flush — soft-close AuctionExtension va
            # denormalizatsiya hisobiga kerak (qulf saqlanadi, commit emas).
            self.db.flush()

            auction.updated_at = datetime.now(UTC)
            self._apply_soft_close_extension(auction, returned_bid.id)
            self._refresh_denormalized_counts(auction)

            # Xato stavka belgisi (bloklamaydi) — frontend tasdiq oynasi uchun.
            returned_bid.high_bid_warning = payload.amount > price_before * TYPO_WARNING_MULTIPLIER
            if returned_bid.high_bid_warning:
                logger.info(
                    "Yuqori stavka: auksion=%s bidder=%s amount=%s (oldingi narx=%s)",
                    auction.id,
                    bidder.id,
                    payload.amount,
                    price_before,
                )

            self.db.add(auction)
            self.db.commit()
        except Exception:
            # Qulfni darhol bo'shatish — kutayotgan bidlar navbatda
            # keraksiz turmasin.
            self.db.rollback()
            raise

        self.db.refresh(returned_bid)
        # high_bid_warning refresh'dan keyin yo'qoladi (mapped emas) — qayta tiklaymiz.
        returned_bid.high_bid_warning = payload.amount > price_before * TYPO_WARNING_MULTIPLIER

        # Real-time: kuzatuvchilarga narx yangilanishini yuboramiz. BEST-EFFORT —
        # tranzaksiyadan KEYIN, xatosi bid'ni buzmaydi (broadcast_threadsafe
        # ichida yutiladi). high_bidder_max / max_amount HECH QACHON yuborilmaydi.
        manager.broadcast_threadsafe(
            auction_id,
            {
                "type": "BID_PLACED",
                "auction_id": auction_id,
                "current_price": str(auction.current_price),
                "highest_bidder_id": auction.highest_bidder_id,
                "end_time": _as_utc(auction.end_time).isoformat(),
            },
        )
        return returned_bid

    def retract_bid(self, bid_id: int, user: User) -> Bid:
        """Foydalanuvchi O'Z bidini qaytarib oladi (typo/xato stavka).

        Cheklovlar (birortasi buzilsa 409):
          - faqat o'z bidi (aks holda 403/404),
          - foydalanuvchi JORIY YETAKCHI bo'lmasligi kerak — yetakchi bidni
            qaytarib narxni buzib ketolmaydi,
          - auksion tugashiga YAQIN bo'lmasligi kerak (soft-close oynasi) —
            oxirgi soniyada retraction bilan raqiblarni aldab bo'lmasin.

        Bid `RETRACTED` bo'ladi, `retracted_by_id` = foydalanuvchi. Joriy narx
        qulf ostida qolgan VALID bidlardan qayta hisoblanadi.
        """
        try:
            bid = self.bids.get(bid_id)
            if bid is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")
            if bid.bidder_id != user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your bid")

            # Auksionni qulflab qayta o'qiymiz — parallel bid/retraction poyga qilmaydi.
            auction = self.auctions.get_for_update(bid.auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if bid.status not in _RETRACTABLE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bid is not in a retractable state",
                )
            if auction.status != AuctionStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Auction is not active",
                )
            if auction.highest_bidder_id == user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Current leader cannot retract a bid",
                )

            now = datetime.now(UTC)
            seconds_until_close = (_as_utc(auction.end_time) - now).total_seconds()
            if seconds_until_close <= settings.soft_close_window_seconds:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Too close to auction end to retract",
                )

            bid.status = BidStatus.RETRACTED
            bid.retracted_by_id = user.id
            self.db.add(bid)
            self._recompute_current_price(auction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(bid)
        return bid

    def invalidate_bid(self, bid_id: int, admin: User, reason: str) -> Bid:
        """Admin bidni bekor qiladi (shill/firibgarlik).

        Joriy yetakchi bid ham bekor qilinishi mumkin — joriy narx qulf ostida
        qolgan VALID bidlardan qayta hisoblanadi. Bid `INVALIDATED` bo'ladi,
        `retracted_by_id` = admin, `retract_reason` = sabab.
        """
        if not is_admin(admin.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required"
            )
        try:
            bid = self.bids.get(bid_id)
            if bid is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bid not found")
            auction = self.auctions.get_for_update(bid.auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if bid.status not in _RETRACTABLE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Bid is not in an invalidatable state",
                )

            bid.status = BidStatus.INVALIDATED
            bid.retracted_by_id = admin.id
            bid.retract_reason = reason
            self.db.add(bid)
            self._recompute_current_price(auction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(bid)
        return bid

    def _recompute_current_price(self, auction: Auction) -> None:
        """Joriy narx/g'olibni qolgan VALID bidlardan qayta hisoblaydi (qulf ostida).

        Retraction/invalidation'dan keyin chaqiriladi. Winning bid = eng yuqori
        VALID bid (proxy bidlar ham VALID bo'lishi mumkin — get_highest_valid_bid
        ularni ham hisobga oladi). VALID bid qolmasa narx starting_price'ga qaytadi.
        `winning_bid.amount == current_price` invarianti saqlanadi.
        """
        self.db.flush()  # holat o'zgarishi navbatdagi so'rovda ko'rinsin
        # Eng yuqori TIRIK bid (VALID/OUTBID). Yetakchi o'chirilgan bo'lsa,
        # keyingi OUTBID bid qayta tiklanadi (VALID qilinadi).
        top = self.bids.get_highest_active_bid(auction.id)
        if top is None:
            auction.current_price = auction.starting_price
            auction.highest_bidder_id = None
            auction.high_bidder_max = None
            auction.winning_bid = None
        else:
            top.status = BidStatus.VALID
            self.db.add(top)
            auction.current_price = top.amount
            auction.highest_bidder_id = top.bidder_id
            auction.high_bidder_max = top.max_amount
            auction.winning_bid = top
        self._refresh_denormalized_counts(auction)
        auction.updated_at = datetime.now(UTC)
        self.db.add(auction)

    def _refresh_denormalized_counts(self, auction: Auction) -> None:
        """bid_count / unique_bidder_count denormalizatsiyasini yangilaydi (qulf ostida)."""
        auction.bid_count = self.bids.count_bids(auction.id)
        auction.unique_bidder_count = self.bids.count_distinct_bidders(auction.id)

    def _resolve_bid(self, auction: Auction, bidder: User, payload: BidCreate) -> Bid:
        """Proxy bidding yechimi. Chaqiruvchiga qaytariladigan Bid'ni beradi.

        Uch holat:
          A) Leader avtomatik himoyalanadi — leader max chaqiruvchining
             ko'ringan bidini bir qadamdan ortiq qoplaydi. Chaqiruvchi bidi
             OUTBID yoziladi, leader nomidan is_proxy=True bid qo'shiladi,
             narx amount+step ga ko'tariladi, leader o'zgarmaydi.
          B) Chaqiruvchi yangi leader bo'ladi — narx = uning ko'ringan bidi,
             high_bidder_max = uning max_amount'i.

        Har holatda winning_bid.amount == current_price bo'lib qoladi, shu
        sababli close/deal mantig'i o'zgarmaydi (yakuniy narx = winning bid).
        """
        amount = payload.amount
        max_amount = payload.max_amount if payload.max_amount is not None else payload.amount
        # Dinamik qadam: joriy narxga qarab jadval qadami, lekin sotuvchi
        # qadamidan past emas (effective_min_increment). Test muhitida jadval
        # o'chirilsa — sotuvchi belgilagan qadam ishlatiladi.
        step = self._min_step(auction)
        leader_id = auction.highest_bidder_id
        leader_max = auction.high_bidder_max

        caller_bid = Bid(
            auction_id=auction.id,
            bidder_id=bidder.id,
            amount=amount,
            max_amount=max_amount,
            is_proxy=False,
            status=BidStatus.VALID,
        )

        # Leader himoyalanadi, agar uning maxi chaqiruvchining ko'ringan bidiga
        # YETSA (teng bo'lsa ham) — teng max'da avval kelgan leader saqlanadi
        # (eBay tie qoidasi). `>= amount + step` bo'lsa, teng max'da leader
        # noto'g'ri yutqazardi (review topilmasi).
        leader_defends = (
            leader_id is not None
            and leader_id != bidder.id
            and leader_max is not None
            and leader_max >= amount
        )

        if leader_defends:
            # Holat A: leader proxy himoyasi. Chaqiruvchi darhol ortda qoldi.
            caller_bid.status = BidStatus.OUTBID
            self.db.add(caller_bid)

            # Narx: chaqiruvchidan bir qadam yuqori, lekin leader maxidan oshmaydi.
            # Teng max'da new_price = amount (leader o'sha narxda ushlab qoladi).
            new_price = min(leader_max, amount + step)
            proxy_bid = Bid(
                auction_id=auction.id,
                bidder_id=leader_id,
                amount=new_price,
                max_amount=leader_max,
                is_proxy=True,
                status=BidStatus.VALID,
            )
            self._demote_current_winner(auction)
            self.db.add(proxy_bid)
            auction.current_price = new_price
            auction.winning_bid = proxy_bid
            # leader_id, high_bidder_max o'zgarmaydi
            self._notify_outbid(auction, bidder.id, new_price)
            return caller_bid

        # Holat B: chaqiruvchi yangi (yoki o'z narxini oshiruvchi) leader.
        self._demote_current_winner(auction)
        self.db.add(caller_bid)
        auction.current_price = amount
        auction.highest_bidder_id = bidder.id
        auction.high_bidder_max = max_amount
        auction.winning_bid = caller_bid
        # Eski leader (agar boshqa odam bo'lsa) ortda qoldi.
        if leader_id is not None and leader_id != bidder.id:
            self._notify_outbid(auction, leader_id, amount)
        return caller_bid

    def _demote_current_winner(self, auction: Auction) -> None:
        """Joriy yutuvchi bidni OUTBID qiladi (yangi yutuvchi belgilanishidan oldin)."""
        previous = auction.winning_bid
        if previous is not None:
            previous.status = BidStatus.OUTBID
            self.db.add(previous)

    def _notify_outbid(self, auction: Auction, user_id: int, new_price: int) -> None:
        """Ortda qolgan bidderga OUTBID bildirishnomasi (bid tranzaksiyasi ichida)."""
        NotificationService(self.db).create(
            user_id=user_id,
            type=NotificationType.OUTBID,
            title="Sizni ortda qoldirishdi",
            body=(
                f"«{auction.item.title if auction.item else 'Lot'}»: taklifingiz ortda qoldi. "
                f"Joriy narx: {format_soum_text(new_price)} soʻm. Yangi taklif qoʻying."
            ),
            payload={"auction_id": auction.id, "current_price": str(new_price)},
        )

    def _activate_if_started_locked(self, auction: Auction) -> None:
        """SCHEDULED -> ACTIVE, commit QILMASDAN.

        Auksion boshlanish vaqti o'tgan bo'lsa aktivlashtiradi. Commit
        qilinmaydi — aks holda bid oqimidagi FOR UPDATE qulfi bo'shab,
        race condition oynasi ochilib qoladi.
        """
        now = datetime.now(UTC)
        if (
            auction.status == AuctionStatus.SCHEDULED
            and _as_utc(auction.start_time) <= now
            and _as_utc(auction.end_time) > now
        ):
            assert_transition(auction.status, AuctionStatus.ACTIVE)
            auction.status = AuctionStatus.ACTIVE
            auction.item.status = ItemStatus.ACTIVE
            # Original muddat hali o'rnatilmagan bo'lsa (eski yozuvlar) — o'rnatamiz.
            if auction.original_end_time is None:
                auction.original_end_time = auction.end_time
            self.db.add(auction)

    def _validate_bid(self, auction: Auction, bidder: User, payload: BidCreate) -> None:
        if auction.seller_id == bidder.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot bid on your own item",
            )
        if auction.status != AuctionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auction is not active",
            )
        if auction.pricing_mode == PricingMode.DESCENDING:
            # Golland auksionida bid yo'q: narx vaqt bilan pasayadi, birinchi xarid yutadi.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bidding is not available in a descending auction; buy at the current price",
            )

        now = datetime.now(UTC)
        if _as_utc(auction.start_time) > now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auction has not started",
            )
        if _as_utc(auction.end_time) <= now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auction has ended",
            )

        # Amaldagi minimal qadam: sotuvchi qadami bilan dinamik jadval qadamining
        # kattarog'i (sotuvchi faqat yuqoriroq qadam qo'ya oladi).
        step = self._min_step(auction)
        minimum_next_bid = auction.current_price + step
        if payload.amount < minimum_next_bid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bid must meet the minimum bid increment",
            )

    def _min_step(self, auction: Auction) -> int:
        """Amaldagi minimal stavka qadami (tiyin).

        Jadval yoqilgan bo'lsa — max(sotuvchi qadami, narxga mos jadval qadami);
        o'chirilgan bo'lsa (masalan test muhiti) — sotuvchi belgilagan qadam.
        """
        if settings.tiered_bid_increment_enabled:
            return effective_min_increment(auction.current_price, auction.minimum_bid_increment)
        return auction.minimum_bid_increment

    def _apply_soft_close_extension(self, auction: Auction, triggering_bid_id: int) -> None:
        """Anti-sniping: tugashga oz qolganda kelgan bid muddatni uzaytiradi.

        Tugashga `soft_close_window_seconds` (120s) yoki kamroq qolganda
        valid bid kelsa, `end_time` `soft_close_extension_seconds` (120s)
        ga suriladi. Maqsad: oxirgi soniyada urib olishning (sniping)
        oldini olish — har kim javob berishga ulguradi.

        Har uzaytirish `AuctionExtension` yozuvi bilan hujjatlanadi
        (old/new end_time, qaysi bid qo'zg'atgani) — audit va ko'rsatish uchun.

        CHEKLOV: uzaytirish cheksiz emas. Auksion ko'pi bilan
        `max_soft_close_extensions` marta uzaytiriladi (har uzaytirishda
        `extension_count += 1`). Limitga yetganda oxirgi soniyadagi bid
        muddatni SURMAYDI — auksion o'z vaqtida yopiladi. Aks holda ikki
        raqib navbatma-navbat bid qo'yib auksionni cheksiz cho'zishi mumkin edi.
        """
        now = datetime.now(UTC)
        end_time = _as_utc(auction.end_time)
        seconds_until_close = (end_time - now).total_seconds()

        within_window = 0 < seconds_until_close <= settings.soft_close_window_seconds
        under_limit = auction.extension_count < settings.max_soft_close_extensions

        if within_window and under_limit:
            new_end_time = end_time + timedelta(seconds=settings.soft_close_extension_seconds)
            self.db.add(
                AuctionExtension(
                    auction_id=auction.id,
                    old_end_time=end_time,
                    new_end_time=new_end_time,
                    triggered_by_bid_id=triggering_bid_id,
                )
            )
            auction.end_time = new_end_time
            auction.extension_count += 1
