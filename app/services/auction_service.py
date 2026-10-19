from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.bid import Bid
from app.models.deal import Deal
from app.models.enums import (
    AuctionStatus,
    BidStatus,
    ItemStatus,
    ListingType,
    NotificationType,
    PricingMode,
)
from app.models.item import Item
from app.models.user import User
from app.money import calc_dutch_step
from app.realtime import manager
from app.repositories.auction_repository import AuctionRepository
from app.repositories.bid_repository import BidRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.auction import (
    AuctionCreate,
    AuctionPricingUpdate,
    AuctionRelist,
    buy_now_window_open,
)
from app.schemas.deal import DealRead
from app.services.auction_state import (
    SELLER_ALLOWED_TARGETS,
    InvalidAuctionTransition,
    assert_transition,
)
from app.services.deal_service import DealService
from app.services.notification_service import NotificationService
from app.services.price_schedule import descending_price_at

# Second-chance offer amal qilish muddati: reserve bajarilmagach sotuvchiga
# eng yuqori bidderga sotish taklifi shu muddat ichida ochiq turadi.
SECOND_CHANCE_TTL = timedelta(hours=24)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _validate_pricing(starting: int, reserve: int | None, buy_now: int | None) -> None:
    """Narxlar o'zaro mantiqiy bo'lishi shart (400).

    Buy-now boshlang'ich narxdan YUQORI bo'lishi kerak — teng bo'lsa auksion
    ma'nosiz (birinchi xaridor darhol qat'iy narxda oladi). Rezervdan past
    buy-now esa sotuvchi "shu narxdan pastga sotmayman" degan narxdan arzonga
    sotib yuborardi.
    """
    if reserve is not None and reserve < starting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reserve price cannot be below the starting price",
        )
    if buy_now is None:
        return
    if buy_now <= starting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Buy now price must be above the starting price",
        )
    if reserve is not None and buy_now < reserve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Buy now price cannot be below the reserve price",
        )


def _validate_mode_pricing(
    mode: PricingMode, starting: int, reserve: int | None, buy_now: int | None
) -> None:
    """Narx yo'nalishiga qarab narxlar mantiqi (400).

    Pasayuvchi auksionda rezerv — narxning PASTKI CHEGARASI: majburiy va boshlang'ich
    narxdan qat'iy past (aks holda narx umuman pasaymaydi yoki nolga tushadi).
    O'suvchi auksionda — oldingi qoidalar (`_validate_pricing`).
    """
    if mode == PricingMode.DESCENDING:
        if reserve is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A descending auction requires a reserve price (price floor)",
            )
        if reserve >= starting:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Price floor must be below the starting price",
            )
        return
    _validate_pricing(starting, reserve, buy_now)


# Golland zaxira bosqichi: 3 kun, narx har soatda tushadi va ~60 soatda chegaraga
# yetadi (oxirgi ~12 soat — chegarada, oxirgi imkoniyat sifatida).
DUTCH_FALLBACK_DAYS = 3
DUTCH_FALLBACK_INTERVAL_MINUTES = 60
DUTCH_FALLBACK_STEPS = 60


def _validate_dutch_fallback(starting: int, floor: int | None) -> None:
    """Golland zaxirasi chegarasi boshlang'ich narxdan past bo'lishi shart (400)."""
    if floor is not None and floor >= starting:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dutch fallback floor must be below the starting price",
        )


class AuctionService:
    """Winner resolution and settlement workflow.

    Future production work belongs here: reserve strategies,
    fraud checks, notifications, and background scheduling.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.auctions = AuctionRepository(db)

    def create_auction(self, seller: User, item: Item, payload: AuctionCreate) -> Auction:
        allowed_item_statuses = {ItemStatus.DRAFT, ItemStatus.SCHEDULED}
        if item.status not in allowed_item_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Auction can only be created for a draft or scheduled item",
            )
        if item.listing_type == ListingType.OFFER:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Item is already published as an offer listing",
            )
        if item.quantity_total != 1:
            # Auksion bitta g'olib = bitta dona. Ko'p donali e'lon — taklif rejimida.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An auction sells exactly one unit; use an offer listing for quantity",
            )

        reserve = payload.reserve_price if payload.reserve_price is not None else item.reserve_price
        _validate_mode_pricing(
            payload.pricing_mode, item.starting_price, reserve, payload.buy_now_price
        )
        _validate_dutch_fallback(item.starting_price, payload.dutch_fallback_floor)

        now = datetime.now(UTC)
        auction_status = (
            AuctionStatus.ACTIVE if _as_utc(payload.start_time) <= now else AuctionStatus.SCHEDULED
        )
        return self.auctions.create(seller, item, payload, auction_status)

    def update_pricing(
        self, auction_id: int, seller: User, payload: AuctionPricingUpdate
    ) -> Auction:
        """Sotuvchi narx rejimini auksion BOSHLANGUNGA QADAR o'zgartiradi.

        Boshlangach (bid yoki xarid bo'lishi mumkin) qoidalarni almashtirish ishtirokchilarga
        nisbatan adolatsiz — 409. Qulf ostida tekshiriladi: boshlanish lahzasidagi poyga
        (activate + update) bir vaqtda o'tmaydi.
        """
        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if auction.seller_id != seller.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not your auction"
                )
            now = datetime.now(UTC)
            if auction.status != AuctionStatus.SCHEDULED or _as_utc(auction.start_time) <= now:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Pricing can only be changed before the auction starts",
                )
            _validate_mode_pricing(
                payload.pricing_mode,
                auction.starting_price,
                payload.reserve_price,
                payload.buy_now_price,
            )
            _validate_dutch_fallback(auction.starting_price, payload.dutch_fallback_floor)

            auction.pricing_mode = payload.pricing_mode
            auction.price_decrement = payload.price_decrement
            auction.price_drop_interval_minutes = payload.price_drop_interval_minutes
            auction.reserve_price = payload.reserve_price
            auction.buy_now_price = payload.buy_now_price
            auction.dutch_fallback_floor = payload.dutch_fallback_floor
            self.db.add(auction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.db.refresh(auction)
        return auction

    def activate_if_started(self, auction_id: int) -> bool:
        """SCHEDULED -> ACTIVE (boshlanish vaqti kelgan bo'lsa). O'zi commit qiladi."""
        try:
            auction = self.auctions.get_for_update(auction_id)
            activated = auction is not None and self._activate_locked(auction, datetime.now(UTC))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return activated

    @staticmethod
    def _activate_locked(auction: Auction, now: datetime) -> bool:
        """Qulf ostida faollashtirish, COMMIT QILMAYDI (buy-now oqimi ichida ham)."""
        if auction.status != AuctionStatus.SCHEDULED or _as_utc(auction.start_time) > now:
            return False
        assert_transition(auction.status, AuctionStatus.ACTIVE)
        auction.status = AuctionStatus.ACTIVE
        auction.item.status = ItemStatus.ACTIVE
        if auction.original_end_time is None:
            auction.original_end_time = auction.end_time
        return True

    def cancel_as_admin(self, auction_id: int) -> Auction:
        """Admin auksionni bekor qiladi (moderatsiya, firibgarlik).

        Sotuvchidan farqli, bidli auksionni ham bekor qila oladi. Qator FOR UPDATE
        bilan qulflanadi va o'tish state machine orqali (yakunlangan auksion — 409);
        tovar ham bekor qilinadi, aks holda e'lon katalogda "faol" bo'lib qolardi.
        """
        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            try:
                assert_transition(auction.status, AuctionStatus.CANCELLED)
            except InvalidAuctionTransition as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
            auction.status = AuctionStatus.CANCELLED
            auction.item.status = ItemStatus.CANCELLED
            self.db.add(auction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(auction)
        return auction

    def buy_now(
        self,
        auction_id: int,
        buyer: User,
        *,
        ip: str | None = None,
        device_id: str | None = None,
        user_agent: str | None = None,
    ) -> Auction:
        """Xaridor lotni buy-now narxida darhol sotib oladi.

        Option B: rezerv narxga yetilguncha ochiq (rezervsiz auksionda — birinchi
        taklifgacha); qoida `buy_now_window_open` da. Mavjud bidlar OUTBID bo'ladi.
        Natija oddiy g'alaba bilan bir xil: buy-now narxida VALID bid yoziladi,
        auksion ENDED bo'ladi va mavjud deal oqimi o'zgarishsiz ishlaydi.

        Auksion qatori FOR UPDATE bilan qulflanadi — parallel bid yoki ikkinchi
        buy-now poyga qilmaydi: kechikkani qulfdan keyin ENDED holatni ko'rib 409 oladi.
        """
        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if auction.seller_id == buyer.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot buy your own item"
                )
            now = datetime.now(UTC)
            # Boshlanish vaqti kelgan, lekin hali faollashtirilmagan — qulf ostida faollashtiramiz
            # (bid oqimidagi kabi; closer tik'ini kutmasdan).
            self._activate_locked(auction, now)
            # Bid validatsiyasi (`BidService._validate_bid`) bilan bir xil vaqt oynasi:
            # boshlanmagan yoki muddati o'tgan (closer hali yopmagan) lot sotilmaydi.
            if (
                auction.status != AuctionStatus.ACTIVE
                or _as_utc(auction.start_time) > now
                or _as_utc(auction.end_time) <= now
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Auction is not active"
                )
            bids = BidRepository(self.db)
            if auction.pricing_mode == PricingMode.DESCENDING:
                # Golland auksioni: narx QULF OSTIDA, shu lahzadagi vaqtdan hisoblanadi —
                # bazadagi qiymatga yoki fon vazifasiga tayanilmaydi. Narx faqat pasayadi,
                # shuning uchun xaridor sahifada ko'rganidan ko'p to'lamaydi.
                assert auction.price_decrement and auction.price_drop_interval_minutes
                assert auction.reserve_price is not None
                price = descending_price_at(
                    starting_price=auction.starting_price,
                    price_decrement=auction.price_decrement,
                    interval_minutes=auction.price_drop_interval_minutes,
                    floor_price=auction.reserve_price,
                    start_time=auction.start_time,
                    at=now,
                )
            else:
                if auction.buy_now_price is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Buy now is not available for this auction",
                    )
                # Option B: rezervga yetguncha ochiq (rezervsiz — birinchi taklifgacha).
                # Ochiq qoida qulf ostida, bid soni bazadan qayta sanaladi.
                window_open = buy_now_window_open(
                    status=auction.status,
                    buy_now_price=auction.buy_now_price,
                    reserve_price=auction.reserve_price,
                    current_price=auction.current_price,
                    bid_count=bids.count_bids(auction.id),
                )
                # Yashirin himoya: ko'rinadigan narx rezervdan past bo'lsa ham yetakchining
                # proxy max'i rezervni qoplagan bo'lishi mumkin — u allaqachon rezerv narxida
                # olishga rozi. Buy-now uni chetlab o'tmasin. Xabar umumiy: max oshkor bo'lmaydi.
                committed = (
                    auction.reserve_price is not None
                    and auction.high_bidder_max is not None
                    and auction.high_bidder_max >= auction.reserve_price
                )
                if not window_open or committed:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Buy now is no longer available for this auction",
                    )

                price = auction.buy_now_price
            # Mavjud bidlar ortda qoladi: joriy yutuvchi bid OUTBID, bidderlarga xabar.
            outbid_users = set(bids.list_bidder_ids(auction.id)) - {buyer.id}
            if auction.winning_bid is not None:
                auction.winning_bid.status = BidStatus.OUTBID
                self.db.add(auction.winning_bid)
            bid = Bid(
                auction_id=auction.id,
                bidder_id=buyer.id,
                amount=price,
                max_amount=price,
                is_proxy=False,
                status=BidStatus.VALID,
                ip=ip,
                device_id=device_id,
                user_agent=user_agent,
            )
            self.db.add(bid)
            self.db.flush()

            auction.current_price = price
            auction.highest_bidder_id = buyer.id
            auction.high_bidder_max = price
            auction.winner_id = buyer.id
            auction.winning_bid = bid
            auction.bid_count = bids.count_bids(auction.id)
            auction.unique_bidder_count = bids.count_distinct_bidders(auction.id)

            assert_transition(auction.status, AuctionStatus.ENDED)
            auction.status = AuctionStatus.ENDED
            auction.closed_at = now
            # Muddatdan oldin yakunlandi: end_time haqiqiy tugash vaqtiga tenglanadi
            # (ro'yxat tartibi, sanoq). Asl muddat original_end_time'da qoladi.
            auction.end_time = now
            auction.item.status = ItemStatus.SOLD
            self.db.add(auction)
            self.db.flush()
            DealService(self.db).create_deal_for_winning_auction(auction)

            notifier = NotificationService(self.db)
            notifier.create(
                user_id=buyer.id,
                type=NotificationType.WON,
                title="Mahsulotni sotib oldingiz",
                body="Mahsulot «hoziroq sotib olish» narxida sizniki. To'lovni amalga oshiring.",
                payload={"auction_id": auction.id, "final_price": str(price)},
            )
            notifier.create(
                user_id=auction.seller_id,
                type=NotificationType.SOLD,
                title="Mahsulotingiz sotildi",
                body="Xaridor mahsulotni «hoziroq sotib olish» narxida sotib oldi.",
                payload={"auction_id": auction.id, "final_price": str(price)},
            )
            for user_id in sorted(outbid_users):
                notifier.create(
                    user_id=user_id,
                    type=NotificationType.OUTBID,
                    title="Lot sotildi",
                    body=(
                        "Boshqa xaridor lotni «hoziroq sotib olish» narxida sotib oldi — "
                        "auksion yakunlandi."
                    ),
                    payload={"auction_id": auction.id, "final_price": str(price)},
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(auction)
        # Kuzatuvchilar sahifasi darhol "yakunlangan" holatga o'tsin (best-effort).
        manager.broadcast_threadsafe(
            auction_id,
            {
                "type": "BUY_NOW",
                "auction_id": auction_id,
                "current_price": str(auction.current_price),
                "highest_bidder_id": auction.highest_bidder_id,
                "end_time": _as_utc(auction.end_time).isoformat(),
            },
        )
        return auction

    def relist(self, auction_id: int, seller: User, payload: AuctionRelist) -> Auction:
        """Sotilmagan lotni yangi narx/muddat bilan qayta joylaydi.

        Faqat sotilmay tugagan auksion: ENDED + g'olibsiz (bid bo'lmagan) yoki
        RESERVE_NOT_MET. Har item'da bitta auksion bo'lgani uchun e'lon nusxa
        ko'chiriladi (yangi item + yangi ACTIVE auksion, bitta tranzaksiyada).

        RESERVE_NOT_MET'da ochiq second-chance taklifi YOPILADI: aks holda
        sotuvchi qayta joylab, keyin eski taklifni ham qabul qilib, bitta
        tovarni ikki xaridorga sotishi mumkin edi.

        Eski auksion FOR UPDATE bilan qulflanadi — ikki parallel relist
        navbatma-navbat bajariladi, ikkinchisi tayyor nusxani ko'rib 409 oladi
        (items.relisted_from_id UNIQUE — oxirgi himoya qatlami).
        """
        try:
            old = self.auctions.get_for_update(auction_id)
            if old is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if old.seller_id != seller.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not your auction"
                )
            unsold = (
                old.status == AuctionStatus.ENDED and old.winner_id is None
            ) or old.status == AuctionStatus.RESERVE_NOT_MET
            if not unsold:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only an unsold auction can be relisted",
                )
            items = ItemRepository(self.db)
            if items.get_relist_of(old.item_id) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This listing has already been relisted",
                )
            _validate_mode_pricing(
                payload.pricing_mode,
                payload.starting_price,
                payload.reserve_price,
                payload.buy_now_price,
            )
            _validate_dutch_fallback(payload.starting_price, payload.dutch_fallback_floor)

            now = datetime.now(UTC)
            if (
                old.second_chance_expires_at is not None
                and _as_utc(old.second_chance_expires_at) > now
            ):
                old.second_chance_expires_at = now
                self.db.add(old)

            new_item = items.clone_for_relist(
                old.item,
                starting_price=payload.starting_price,
                reserve_price=payload.reserve_price,
            )
            create = AuctionCreate(
                item_id=new_item.id,
                start_time=now,
                duration_days=payload.duration_days,
                minimum_bid_increment=payload.minimum_bid_increment,
                reserve_price=payload.reserve_price,
                buy_now_price=payload.buy_now_price,
                pricing_mode=payload.pricing_mode,
                price_decrement=payload.price_decrement,
                price_drop_interval_minutes=payload.price_drop_interval_minutes,
                dutch_fallback_floor=payload.dutch_fallback_floor,
            )
            # Repository create bitta commit bilan hammasini yozadi (eski
            # auksion, nusxa item, yangi auksion) — qisman holat qolmaydi.
            return self.auctions.create(seller, new_item, create, AuctionStatus.ACTIVE)
        except Exception:
            self.db.rollback()
            raise

    def set_status_by_seller(self, auction_id: int, seller: User, target: AuctionStatus) -> Auction:
        """Sotuvchi qo'lda holat o'zgartiradi (amalda: bekor qilish).

        Ilgari bu endpoint sotuvchiga ISTALGAN holatni yozishga ruxsat
        berardi — jonli auksionni `ended` qilib deal/g'olib oqimini
        chetlab o'tish, yoki bidli auksionni `cancelled` qilib bidlarni
        kuydirish mumkin edi. Endi:
          - faqat SELLER_ALLOWED_TARGETS (bekor qilish) ruxsat etiladi
          - o'tish state machine bilan tekshiriladi
          - bidli auksionni bekor qilib bo'lmaydi
        Auksion qatori FOR UPDATE bilan qulflanadi — bekor qilish va
        parallel bid o'zaro poyga qilmaydi.
        """
        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if auction.seller_id != seller.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not your auction"
                )
            if target not in SELLER_ALLOWED_TARGETS:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Seller can only cancel an auction",
                )

            try:
                assert_transition(auction.status, target)
            except InvalidAuctionTransition as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

            has_bids = BidRepository(self.db).get_highest_valid_bid(auction.id) is not None
            if has_bids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot cancel an auction that already has bids",
                )

            auction.status = target
            auction.item.status = ItemStatus.CANCELLED
            self.db.add(auction)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(auction)
        return auction

    def close_auction(self, auction_id: int) -> Auction:
        """Auksionni yopadi: g'olibni aniqlab, deal yaratadi.

        # TODO: fon vazifasiga ko'chirilsin (end_time bo'yicha avtomatik).

        Auksion qatori FOR UPDATE bilan qulflanadi — yopish paytida
        parallel bid kelib g'olibni o'zgartira olmaydi. Faqat ACTIVE
        auksion yopiladi (idempotent: qayta yopish yoki boshlanmaganini
        yopish 409 beradi). Holat o'zgarishlari state machine orqali.
        """
        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if auction.status != AuctionStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only an active auction can be closed",
                )

            now = datetime.now(UTC)
            winning_bid = BidRepository(self.db).get_highest_valid_bid(auction.id)

            if winning_bid is None:
                assert_transition(auction.status, AuctionStatus.ENDED)
                auction.status = AuctionStatus.ENDED
                auction.winner_id = None
                auction.highest_bidder_id = None
                auction.closed_at = now
                auction.item.status = ItemStatus.CANCELLED
                self.db.add(auction)
                if (
                    auction.dutch_fallback_floor is not None
                    and auction.pricing_mode == PricingMode.ASCENDING
                    and auction.continued_as_auction_id is None
                ):
                    # Sotuvchi oldindan rozi: lot yo'qolmaydi — shu tranzaksiyada
                    # pasayuvchi bosqichga o'tadi (qisman holat qolmaydi).
                    self._continue_as_dutch(auction, now)
                self.db.commit()
                self.db.refresh(auction)
                return auction

            auction.winning_bid = winning_bid
            auction.highest_bidder_id = winning_bid.bidder_id
            auction.winner_id = winning_bid.bidder_id

            if auction.reserve_price is not None and winning_bid.amount < auction.reserve_price:
                # Reserve bajarilmadi: auksionni RESERVE_NOT_MET qilamiz va
                # sotuvchiga second-chance taklif beramiz — u eng yuqori bidderga
                # sotishga rozi bo'lsa (24 soat ichida) deal yaratiladi.
                assert_transition(auction.status, AuctionStatus.RESERVE_NOT_MET)
                auction.status = AuctionStatus.RESERVE_NOT_MET
                auction.closed_at = now
                auction.second_chance_offered_at = now
                auction.second_chance_expires_at = now + SECOND_CHANCE_TTL
                auction.item.status = ItemStatus.CANCELLED
                self.db.add(auction)
                NotificationService(self.db).create(
                    user_id=auction.seller_id,
                    type=NotificationType.SECOND_CHANCE,
                    title="Rezerv narxga yetilmadi",
                    body=(
                        "Eng yuqori taklif rezerv narxdan past. Xohlasangiz eng yuqori "
                        "bidderga shu narxda sotishingiz mumkin (24 soat ichida)."
                    ),
                    payload={
                        "auction_id": auction.id,
                        "highest_bid": str(winning_bid.amount),
                        "expires_at": auction.second_chance_expires_at.isoformat(),
                    },
                )
                self.db.commit()
                self.db.refresh(auction)
                return auction

            assert_transition(auction.status, AuctionStatus.ENDED)
            auction.status = AuctionStatus.ENDED
            auction.closed_at = now
            auction.item.status = ItemStatus.SOLD
            self.db.add(auction)
            self.db.flush()
            DealService(self.db).create_deal_for_winning_auction(auction)
            # G'olib va sotuvchi xabardor qilinadi (tranzaksiya ichida, atomik).
            notifier = NotificationService(self.db)
            notifier.create(
                user_id=winning_bid.bidder_id,
                type=NotificationType.WON,
                title="Auksionda yutdingiz!",
                body="Tabriklaymiz — mahsulotni yutib oldingiz. To'lovni amalga oshiring.",
                payload={"auction_id": auction.id, "final_price": str(auction.current_price)},
            )
            notifier.create(
                user_id=auction.seller_id,
                type=NotificationType.SOLD,
                title="Mahsulotingiz sotildi",
                body="Auksioningiz g'olib bilan yakunlandi.",
                payload={"auction_id": auction.id, "final_price": str(auction.current_price)},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(auction)
        return auction

    def _continue_as_dutch(self, auction: Auction, now: datetime) -> Auction | None:
        """Taklifsiz tugagan o'suvchi auksionni 3 kunlik pasayuvchi auksionga o'tkazadi.

        COMMIT QILMAYDI — `close_auction` tranzaksiyasi (auksion qulfi ostida) ichida.
        Har item'da bitta auksion (`auctions.item_id` UNIQUE), shuning uchun qayta joylash
        mexanizmi qo'llanadi: e'lon nusxasi (`relisted_from_id`) + yangi DESCENDING auksion.
        Narx asl boshlang'ich narxdan boshlanadi va har soatda tushib ~60 soatda sotuvchi
        rozi bo'lgan chegaraga yetadi; qadam `app/money.calc_dutch_step` da.
        """
        floor = auction.dutch_fallback_floor
        start = auction.starting_price
        items = ItemRepository(self.db)
        if floor is None or floor >= start or items.get_relist_of(auction.item_id) is not None:
            return None

        new_item = items.clone_for_relist(auction.item, starting_price=start, reserve_price=None)
        end = now + timedelta(days=DUTCH_FALLBACK_DAYS)
        continuation = Auction(
            item_id=new_item.id,
            seller_id=auction.seller_id,
            start_time=now,
            end_time=end,
            original_end_time=end,
            duration_days=DUTCH_FALLBACK_DAYS,
            status=AuctionStatus.ACTIVE,
            starting_price=start,
            current_price=start,
            minimum_bid_increment=auction.minimum_bid_increment,
            reserve_price=floor,
            pricing_mode=PricingMode.DESCENDING,
            price_decrement=calc_dutch_step(start, floor, DUTCH_FALLBACK_STEPS),
            price_drop_interval_minutes=DUTCH_FALLBACK_INTERVAL_MINUTES,
        )
        new_item.status = ItemStatus.ACTIVE
        new_item.listing_type = ListingType.AUCTION
        new_item.published_at = now
        self.db.add(continuation)
        self.db.flush()
        auction.continued_as_auction_id = continuation.id

        watchers = WatchlistRepository(self.db).copy_to_auction(auction.id, continuation.id)
        notifier = NotificationService(self.db)
        payload = {"auction_id": continuation.id, "previous_auction_id": auction.id}
        notifier.create(
            user_id=auction.seller_id,
            type=NotificationType.DUTCH_STARTED,
            title="Lot pasayuvchi auksionga oʻtdi",
            body=(
                "Taklif tushmadi — roziligingizga koʻra lot 3 kunlik pasayuvchi auksionda: "
                "narx har soatda tushadi, birinchi xaridor sotib oladi."
            ),
            payload=payload,
        )
        for user_id in watchers:
            if user_id == auction.seller_id:
                continue
            notifier.create(
                user_id=user_id,
                type=NotificationType.DUTCH_STARTED,
                title="Kuzatgan lotingiz arzonlashmoqda",
                body="Lot pasayuvchi auksionga oʻtdi: narx har soatda tushadi.",
                payload=payload,
            )
        return continuation

    def accept_second_chance(self, auction_id: int, seller: User) -> Auction:
        """Sotuvchi second-chance taklifni qabul qiladi — eng yuqori bidderga sotadi.

        Reserve bajarilmagach (RESERVE_NOT_MET) sotuvchi taklif muddati (24 soat)
        ichida rozi bo'lsa: auksion ENDED bo'ladi, g'olib = eng yuqori VALID
        bidder, deal yaratiladi (mavjud close oqimi bilan bir xil), g'olib va
        sotuvchi xabardor qilinadi. Muddat o'tgan yoki holat noto'g'ri bo'lsa 409.

        Auksion qatori FOR UPDATE bilan qulflanadi.
        """
        try:
            auction = self.auctions.get_for_update(auction_id)
            if auction is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found"
                )
            if auction.seller_id != seller.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not your auction"
                )
            if auction.status != AuctionStatus.RESERVE_NOT_MET:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No active second-chance offer for this auction",
                )

            now = datetime.now(UTC)
            if (
                auction.second_chance_expires_at is None
                or _as_utc(auction.second_chance_expires_at) <= now
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Second-chance offer has expired",
                )

            winning_bid = BidRepository(self.db).get_highest_valid_bid(auction.id)
            if winning_bid is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No valid bids to accept",
                )

            auction.winning_bid = winning_bid
            auction.highest_bidder_id = winning_bid.bidder_id
            auction.winner_id = winning_bid.bidder_id

            assert_transition(auction.status, AuctionStatus.ENDED)
            auction.status = AuctionStatus.ENDED
            auction.closed_at = now
            auction.item.status = ItemStatus.SOLD
            self.db.add(auction)
            self.db.flush()
            DealService(self.db).create_deal_for_winning_auction(auction)

            notifier = NotificationService(self.db)
            notifier.create(
                user_id=winning_bid.bidder_id,
                type=NotificationType.WON,
                title="Auksionda yutdingiz!",
                body="Sotuvchi taklifingizni qabul qildi. To'lovni amalga oshiring.",
                payload={"auction_id": auction.id, "final_price": str(auction.current_price)},
            )
            notifier.create(
                user_id=auction.seller_id,
                type=NotificationType.SOLD,
                title="Mahsulotingiz sotildi",
                body="Second-chance taklif qabul qilindi — auksion g'olib bilan yakunlandi.",
                payload={"auction_id": auction.id, "final_price": str(auction.current_price)},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(auction)
        return auction

    def get_or_create_order_for_winner(self, auction: Auction) -> Deal | None:
        if auction.winner_id is None:
            return None
        return DealService(self.db).create_deal_for_winning_auction(auction)


def serialize_order(deal: Deal | None) -> DealRead | None:
    if deal is None:
        return None
    return DealRead.model_validate(deal)


AuctionSettlementService = AuctionService
