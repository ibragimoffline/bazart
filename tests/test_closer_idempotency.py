"""Closer idempotentligi: bir auksion ikki marta parallel yopilsa ham AYNAN
BITTA deal yaratiladi.

NEGA ALOHIDA FAYL: qolgan testlar bitta ulashilgan sessiya (bitta ulanish)
orqali ketma-ket ishlaydi — ular haqiqiy parallellikni SINAB KO'RA OLMAYDI.
Idempotentlikni isbotlash uchun har thread'da ALOHIDA DB ulanishi kerak, aks
holda hech qanday raqobat yuzaga kelmaydi.

Ssenariy: muddati o'tgan (end_time o'tmishda), bidli FAOL auksion. Ikkita
alohida sessiya `threading.Barrier` bilan bir vaqtda auksionni yopishga
uriladi. `close_auction` auksion qatorini FOR UPDATE bilan qulflaydi va faqat
ACTIVE holatni yopadi: birinchi urinish g'olib/deal yaratib ENDED qiladi,
ikkinchisi qulf bo'shagach ACTIVE emasligini ko'radi va HTTPException oladi
(closer buni jimgina yutadi). Natijada deal jadvalida `auction_id` UNIQUE —
ikki deal INSERT bo'lsa DB xato beradi. Regressiyada (qulf yo'q yoki status
tekshiruvi buzuq) ikkinchi yopish ham deal yaratmoqchi bo'lib bu test yiqiladi.
"""

import threading
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.deal import Deal
from app.models.enums import (
    AuctionStatus,
    BidStatus,
    ItemCondition,
    ItemStatus,
    UserRole,
)
from app.models.item import Item
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.services.auction_service import AuctionService
from tests.conftest import TEST_PASSWORD

STARTING_PRICE = 100_000  # tiyin
BID_AMOUNT = 110_000  # tiyin


def _seed_due_auction_with_bid(db: Session) -> int:
    """Muddati o'tgan, bitta VALID bidli FAOL auksion yaratadi, id qaytaradi.

    Auksion to'g'ridan-to'g'ri model orqali seed qilinadi (API emas): shunda
    `end_time` ni o'tmishga qo'yib, bidni VALID holatda joylashimiz mumkin —
    API bo'lsa muddati o'tgan auksionga bid qabul qilmasdi.
    """
    seller = User(
        email="seller@closer.test",
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Seller",
        role=UserRole.SELLER,
    )
    bidder = User(
        email="bidder@closer.test",
        hashed_password=hash_password(TEST_PASSWORD),
        full_name="Bidder",
        role=UserRole.USER,
    )
    db.add_all([seller, bidder])
    db.flush()

    item = Item(
        seller_id=seller.id,
        title="Closer item",
        condition=ItemCondition.USED,
        status=ItemStatus.ACTIVE,
        starting_price=STARTING_PRICE,
    )
    db.add(item)
    db.flush()

    now = datetime.now(UTC)
    auction = Auction(
        item_id=item.id,
        seller_id=seller.id,
        start_time=now - timedelta(days=1),
        # Muddati allaqachon o'tgan — closer uni "yopilishi kerak" deb topadi.
        end_time=now - timedelta(minutes=1),
        status=AuctionStatus.ACTIVE,
        starting_price=STARTING_PRICE,
        current_price=BID_AMOUNT,
        minimum_bid_increment=10_000,
        highest_bidder_id=bidder.id,
    )
    db.add(auction)
    db.flush()

    bid = Bid(
        auction_id=auction.id,
        bidder_id=bidder.id,
        amount=BID_AMOUNT,
        max_amount=BID_AMOUNT,
        status=BidStatus.VALID,
    )
    db.add(bid)
    db.flush()

    auction_id = auction.id
    db.commit()
    return auction_id


def test_parallel_close_creates_exactly_one_order(db_session: Session, db_engine: Engine) -> None:
    auction_id = _seed_due_auction_with_bid(db_session)

    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    barrier = threading.Barrier(2)
    results: dict[int, str] = {}
    lock = threading.Lock()

    def close(worker: int) -> None:
        # Har thread — o'z sessiyasi, o'z ulanishi: aynan shu haqiqiy raqobatni
        # (ikki closer bir vaqtda bir auksionni yopishi) yuzaga keltiradi.
        session = SessionMaker()
        try:
            barrier.wait()  # ikkalasi bir vaqtda otiladi
            try:
                AuctionService(session).close_auction(auction_id)
                outcome = "ok"
            except HTTPException:
                # Kutilgan: ikkinchi urinish qulf bo'shagach ACTIVE emasligini
                # ko'radi -> 409. Closer worker aynan shu xatoni jimgina yutadi.
                outcome = "http_error"
            except Exception as exc:  # noqa: BLE001
                outcome = type(exc).__name__
            with lock:
                results[worker] = outcome
        finally:
            session.close()

    threads = [threading.Thread(target=close, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [w for w, o in results.items() if o == "ok"]

    # 1) Kamida bittasi yopdi; UNIQUE buzilishi (dublikat deal INSERT) yoki
    #    kutilmagan xato bo'lmasligi kerak.
    assert len(successes) >= 1, f"hech biri yopmadi: {results}"
    unexpected = {w: o for w, o in results.items() if o not in ("ok", "http_error")}
    assert not unexpected, f"kutilmagan xatolar (idempotent emas?): {unexpected}"

    # 2) Toza sessiyada tekshirish: auksion ENDED va AYNAN bitta deal bor.
    check = SessionMaker()
    try:
        auction = check.get(Auction, auction_id)
        assert auction.status == AuctionStatus.ENDED

        order_count = check.scalar(
            select(func.count()).select_from(Deal).where(Deal.auction_id == auction_id)
        )
        assert order_count == 1, f"kutilgan 1 deal, aslida {order_count}"

        # get_active_by_auction_id ham bittani qaytaradi (dublikat bo'lsa u yerda ham
        # MultipleResultsFound bo'lardi).
        deal = DealRepository(check).get_active_by_auction_id(auction_id)
        assert deal is not None
        assert deal.final_price == BID_AMOUNT
    finally:
        check.close()
