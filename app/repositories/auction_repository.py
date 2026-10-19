from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.enums import AuctionStatus, ItemStatus, ListingType
from app.models.item import Item
from app.models.user import User
from app.schemas.auction import AuctionCreate


class AuctionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        seller: User,
        item: Item,
        payload: AuctionCreate,
        status: AuctionStatus,
    ) -> Auction:
        auction = Auction(
            item_id=item.id,
            seller_id=seller.id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            # Anti-sniping surishidan OLDINGI original muddat — audit uchun.
            original_end_time=payload.end_time,
            duration_days=payload.duration_days,
            status=status,
            starting_price=item.starting_price,
            current_price=item.starting_price,
            minimum_bid_increment=payload.minimum_bid_increment,
            reserve_price=payload.reserve_price
            if payload.reserve_price is not None
            else item.reserve_price,
            buy_now_price=payload.buy_now_price,
            pricing_mode=payload.pricing_mode,
            price_decrement=payload.price_decrement,
            price_drop_interval_minutes=payload.price_drop_interval_minutes,
            dutch_fallback_floor=payload.dutch_fallback_floor,
        )
        item.status = ItemStatus.ACTIVE if status == AuctionStatus.ACTIVE else ItemStatus.SCHEDULED
        item.listing_type = ListingType.AUCTION
        self.db.add(auction)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(auction)
        return auction

    def claim_due_for_ending_soon(self, now: datetime, lead: timedelta) -> list[int]:
        """Eslatma vaqti kelgan faol auksionlarni "band qiladi" va id'larini qaytaradi.

        Bitta UPDATE: `ending_soon_notified_at = now` yoziladi, ichki SELECT esa
        FOR UPDATE SKIP LOCKED — parallel worker (beat + in-process) bir auksionni
        ikki marta olmaydi, bid tranzaksiyasi qulflagan qator esa o'tkazib yuboriladi
        (keyingi tik'da olinadi). Chaqiruvchi darhol commit qiladi — qulf xabar
        yuborish davomida USHLANMAYDI (oxirgi soatdagi bidlar kutib qolmasin).
        """
        due = (
            select(Auction.id)
            .where(
                Auction.status == AuctionStatus.ACTIVE,
                Auction.ending_soon_notified_at.is_(None),
                Auction.end_time > now,
                Auction.end_time <= now + lead,
            )
            .with_for_update(skip_locked=True)
        )
        statement = (
            update(Auction)
            .where(Auction.id.in_(due))
            .values(ending_soon_notified_at=now)
            .returning(Auction.id)
            .execution_options(synchronize_session=False)
        )
        return list(self.db.scalars(statement))

    def list(
        self,
        *,
        status: AuctionStatus | None = AuctionStatus.ACTIVE,
        seller_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Auction]:
        # Faol/rejalashtirilgan — tez tugaydigani birinchi; yakunlanganlar — eng
        # yangisi birinchi (aks holda limit eski lotlar bilan to'lib, sotuvchi
        # yaqinda sotilmay qolgan lotini ko'rmasdi).
        finished = status in (
            AuctionStatus.ENDED,
            AuctionStatus.RESERVE_NOT_MET,
            AuctionStatus.CANCELLED,
        )
        order = Auction.end_time.desc() if finished else Auction.end_time.asc()
        statement = select(Auction).order_by(order).offset(skip).limit(limit)
        if status is not None:
            statement = statement.where(Auction.status == status)
        if seller_id is not None:
            statement = statement.where(Auction.seller_id == seller_id)
        return list(self.db.scalars(statement))

    def get(self, auction_id: int) -> Auction | None:
        return self.db.get(Auction, auction_id)

    def get_for_update(self, auction_id: int) -> Auction | None:
        """Auksion qatorini QULFLAB o'qiydi (SELECT ... FOR UPDATE).

        Bid oqimi uchun. Qulf tranzaksiya tugaguncha (commit/rollback)
        ushlanadi — shu vaqt ichida boshqa tranzaksiya shu qatorni
        o'qiy olmaydi, navbatda kutadi.

        Qulfsiz "o'qi -> tekshir -> yoz" ketma-ketligi lost update beradi:
        ikki bid bir xil current_price ni o'qiydi, ikkalasi ham
        validatsiyadan o'tadi, oxirgi yozuvchi g'olib bo'ladi — natijada
        pastroq taklif yutib, yuqori bid yo'qoladi.

        MUHIM: chaqiruvchi qulf o'rnatilgandan keyin commit QILMASLIGI
        kerak — har qanday commit qulfni bo'shatadi.
        """
        statement = select(Auction).where(Auction.id == auction_id).with_for_update()
        return self.db.scalars(statement).one_or_none()

    def item_has_auction(self, item_id: int) -> bool:
        statement = select(Auction.id).where(Auction.item_id == item_id)
        return self.db.scalar(statement) is not None
