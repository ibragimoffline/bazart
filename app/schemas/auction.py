from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.core.config import settings
from app.models.enums import AuctionStatus, PricingMode
from app.money import TIYIN_PER_SOUM
from app.money.fields import TiyinAmount
from app.services.bid_increment import effective_min_increment
from app.services.price_schedule import descending_price_at, next_price_drop_at


def buy_now_window_open(
    *,
    status: AuctionStatus,
    buy_now_price: int | None,
    reserve_price: int | None,
    current_price: int,
    bid_count: int,
) -> bool:
    """Buy-now oynasi ochiqmi (Option B — rezervgacha). Ochiq ma'lumotlar bo'yicha.

    - Rezerv bor: joriy narx rezervga yetguncha ochiq — bid tushsa ham. Rezervga
      yetilgach yopiladi: sotuvchining "shu narxga sotaman" sharti bajarilgan, endi
      raqobat davom etadi va qat'iy narx uni to'xtatmasligi kerak.
    - Rezerv yo'q: kutadigan chegara yo'q -> birinchi taklifda yopiladi (Option A).

    Bu UI va birinchi tekshiruv uchun. `AuctionService.buy_now` qulf ostida yana
    yashirin proxy max'ni ham tekshiradi (ko'rinadigan narx rezervdan past bo'lsa ham
    yetakchining max'i rezervni qoplagan bo'lishi mumkin).
    """
    if buy_now_price is None or status != AuctionStatus.ACTIVE:
        return False
    if reserve_price is None:
        return bid_count == 0
    return current_price < reserve_price


class PricingModeFields(BaseModel):
    """Narx yo'nalishi maydonlari — auksion yaratish va qayta joylashda umumiy.

    DESCENDING: narx har `price_drop_interval_minutes` da `price_decrement` ga pasayadi;
    pastki chegara — reserve_price (service'da majburiy, boshlang'ichdan past).
    """

    pricing_mode: PricingMode = PricingMode.ASCENDING
    price_decrement: TiyinAmount | None = Field(default=None, gt=0)
    price_drop_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    # Sotuvchi roziligi: taklifsiz tugasa 3 kunlik pasayuvchi auksionga o'tsin; qiymat —
    # o'sha bosqichning pastki chegarasi (boshlang'ichdan past — service tekshiradi).
    dutch_fallback_floor: TiyinAmount | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_pricing_mode(self) -> "PricingModeFields":
        if self.dutch_fallback_floor is not None and self.pricing_mode != PricingMode.ASCENDING:
            raise ValueError("dutch_fallback_floor is only used in an ascending auction")
        if self.pricing_mode == PricingMode.DESCENDING:
            if self.price_decrement is None or self.price_drop_interval_minutes is None:
                raise ValueError(
                    "Descending auction requires price_decrement and price_drop_interval_minutes"
                )
            if getattr(self, "buy_now_price", None) is not None:
                # Pasayuvchi auksionda "sotib olish" — joriy narxda; alohida qat'iy narx yo'q.
                raise ValueError("buy_now_price is not used in a descending auction")
        elif self.price_decrement is not None or self.price_drop_interval_minutes is not None:
            raise ValueError("price_decrement is only used in a descending auction")
        return self


class AuctionCreate(PricingModeFields):
    item_id: int
    start_time: datetime
    # Auksion tugash vaqtini berishning IKKI yo'li (ayni bittasi majburiy):
    #   1) end_time — aniq sana/vaqt (orqaga moslik uchun saqlangan eski yo'l).
    #   2) duration_days — majburiy deadline (3/5/7 kun), mahsulotning asosiy
    #      qoidasi. Berilsa end_time = start_time + kun sifatida hisoblanadi.
    end_time: datetime | None = None
    duration_days: Literal[3, 5, 7] | None = None
    # Pul tiyinda, JSON'da string: {"minimum_bid_increment": "100000"}
    minimum_bid_increment: TiyinAmount = Field(default=TIYIN_PER_SOUM, gt=0)
    reserve_price: TiyinAmount | None = Field(default=None, gt=0)
    # "Hoziroq sotib olish" narxi. Boshlang'ich narxdan yuqori va rezervdan
    # past bo'lmasligi service'da (item narxi bilan) tekshiriladi.
    buy_now_price: TiyinAmount | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_schedule(self) -> "AuctionCreate":
        # end_time va duration_days'dan AYNAN BITTASI berilishi shart.
        if (self.end_time is None) == (self.duration_days is None):
            raise ValueError("Provide exactly one of end_time or duration_days")

        if self.duration_days is not None:
            # duration_days yo'li: end_time'ni hisoblab qo'yamiz — shunda
            # downstream kod (repo/service) faqat payload.end_time'ni o'qiydi.
            self.end_time = self.start_time + timedelta(days=self.duration_days)
        elif self.end_time <= self.start_time:
            raise ValueError("Auction end time must be after start time")

        return self


class PricePoint(BaseModel):
    """Pasayuvchi auksion narx prognozi nuqtasi: `at` paytida narx `price` bo'ladi."""

    at: datetime
    price: TiyinAmount
    # Hozirdan necha to'liq kun keyin (oxirgi nuqta — tugash, kasr kun yaxlitlanmagan).
    days_from_now: int
    is_end: bool = False


class AuctionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    seller_id: int
    start_time: datetime
    end_time: datetime
    duration_days: int | None
    status: AuctionStatus
    starting_price: TiyinAmount
    current_price: TiyinAmount
    minimum_bid_increment: TiyinAmount
    # XAVFSIZLIK: reserve_price qiymati javobda HECH QACHON oshkor bo'lmaydi
    # (exclude=True) — bidderlar rezervni bilib, aynan bir tiyin ustidan bid
    # qo'yib strategiyani buzardi. O'rniga faqat has_reserve/reserve_met.
    reserve_price: TiyinAmount | None = Field(default=None, exclude=True)
    bid_count: int = 0
    unique_bidder_count: int = 0
    buy_now_price: TiyinAmount | None = None
    pricing_mode: PricingMode = PricingMode.ASCENDING
    price_decrement: TiyinAmount | None = None
    price_drop_interval_minutes: int | None = None
    # Golland zaxirasi OMMAGA OSHKOR QILINMAYDI — na chegara, na yoqilganligi: xaridorlar
    # "taklif tushmasa arzonlashadi" deb bilsa, birinchi auksionda taklif bermay kutardi.
    # Faqat sodir bo'lgach `continued_as_auction_id` ko'rinadi.
    dutch_fallback_floor: TiyinAmount | None = Field(default=None, exclude=True)
    continued_as_auction_id: int | None = None
    highest_bidder_id: int | None
    winner_id: int | None
    winning_bid_id: int | None
    original_end_time: datetime | None = None
    closed_at: datetime | None = None
    second_chance_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _live_descending_price(self) -> "AuctionRead":
        """Pasayuvchi auksion: sotilmagan bo'lsa joriy narx VAQTDAN hisoblanadi.

        Bazadagi current_price boshlang'ich narxda qoladi (fon vazifasi narxni
        tushirmaydi). Yakunlangan, sotilmagan auksion — tugash paytidagi narx;
        sotilgan bo'lsa — saqlangan sotuv narxi.
        """
        if self.pricing_mode == PricingMode.DESCENDING and self.winner_id is None:
            self.current_price = self._descending_price(self._price_clock())
        return self

    def _price_clock(self) -> datetime:
        now = datetime.now(UTC)
        end = self.end_time if self.end_time.tzinfo else self.end_time.replace(tzinfo=UTC)
        return min(now, end)

    def _descending_price(self, at: datetime) -> int:
        assert self.price_decrement and self.price_drop_interval_minutes and self.reserve_price
        return descending_price_at(
            starting_price=self.starting_price,
            price_decrement=self.price_decrement,
            interval_minutes=self.price_drop_interval_minutes,
            floor_price=self.reserve_price,
            start_time=self.start_time,
            at=at,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def price_forecast(self) -> list[PricePoint]:
        """Pasayuvchi auksion: kunlik narx prognozi (xaridor "kutsam qancha bo'ladi?").

        Har to'liq kun belgisida va tugash paytida kutilayotgan narx — faqat haqiqiy
        pasayishlar; narx chegaraga yetgach to'xtaydi. DIQQAT: prognoz chegaraga yetsa,
        chegara (rezerv) qiymati ko'rinadi — bu narx shaffofligi uchun ataylab
        (`docs/AUCTION_ENGINE.md` §12). Hisob `price_schedule` orqali — yagona manba.
        """
        if (
            self.pricing_mode != PricingMode.DESCENDING
            or self.winner_id is not None
            or self.status not in (AuctionStatus.ACTIVE, AuctionStatus.SCHEDULED)
        ):
            return []
        now = datetime.now(UTC)
        end = self.end_time if self.end_time.tzinfo else self.end_time.replace(tzinfo=UTC)
        start = self.start_time if self.start_time.tzinfo else self.start_time.replace(tzinfo=UTC)
        base = max(now, start)
        points: list[PricePoint] = []
        last = self._descending_price(base)
        day = 1
        while len(points) < 7:
            at = now + timedelta(days=day)
            is_end = at >= end
            if is_end:
                at = end
            price = self._descending_price(at)
            if price < last:
                points.append(
                    PricePoint(at=at, price=price, days_from_now=(at - now).days, is_end=is_end)
                )
                last = price
            if is_end or price <= (self.reserve_price or 0):
                break
            day += 1
        return points

    @computed_field  # type: ignore[prop-decorator]
    @property
    def next_price_drop_at(self) -> datetime | None:
        """Pasayuvchi auksion: keyingi narx tushishi (faol, chegaraga yetmagan bo'lsa)."""
        if self.pricing_mode != PricingMode.DESCENDING or self.status != AuctionStatus.ACTIVE:
            return None
        assert self.price_decrement and self.price_drop_interval_minutes and self.reserve_price
        nxt = next_price_drop_at(
            starting_price=self.starting_price,
            price_decrement=self.price_decrement,
            interval_minutes=self.price_drop_interval_minutes,
            floor_price=self.reserve_price,
            start_time=self.start_time,
            at=datetime.now(UTC),
        )
        end = self.end_time if self.end_time.tzinfo else self.end_time.replace(tzinfo=UTC)
        return nxt if nxt is not None and nxt < end else None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_reserve(self) -> bool:
        """Auksionda rezerv narx bormi (qiymatni oshkor qilmasdan).

        Pasayuvchi auksionda rezerv — narxning pastki chegarasi, "qoplanadigan"
        shart emas; shuning uchun bu yerda False (UI "zaxira qoplanmagan" demasin).
        """
        return self.reserve_price is not None and self.pricing_mode == PricingMode.ASCENDING

    @computed_field  # type: ignore[prop-decorator]
    @property
    def minimum_next_bid(self) -> TiyinAmount:
        """Server qabul qiladigan eng kichik keyingi bid (tiyin).

        Frontend qadam jadvalini takrorlamasin — aks holda jadval o'zgarganda
        UI ko'rsatgan minimum server rad etadigan summa bo'lib qoladi.
        Hisob `BidService._min_step` bilan bir xil manbadan.
        """
        step = self.minimum_bid_increment
        if settings.tiered_bid_increment_enabled:
            step = effective_min_increment(self.current_price, self.minimum_bid_increment)
        return self.current_price + step

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reserve_met(self) -> bool | None:
        """Rezerv bajarilganmi. Rezerv yo'q bo'lsa None (ha/yo'q ma'nosizmas)."""
        if self.reserve_price is None or self.pricing_mode == PricingMode.DESCENDING:
            return None
        return self.current_price >= self.reserve_price

    @computed_field  # type: ignore[prop-decorator]
    @property
    def buy_now_available(self) -> bool:
        """Hoziroq sotib olish (buy-now) hozir mumkinmi — `buy_now_window_open` (Option B).

        Faqat UI uchun; yakuniy tekshiruv `AuctionService.buy_now` da (qulf ostida).
        """
        if self.pricing_mode == PricingMode.DESCENDING:
            # Golland auksioni: faol bo'lsa har doim joriy narxda sotib olish mumkin.
            return self.status == AuctionStatus.ACTIVE and self.winner_id is None
        return buy_now_window_open(
            status=self.status,
            buy_now_price=self.buy_now_price,
            reserve_price=self.reserve_price,
            current_price=self.current_price,
            bid_count=self.bid_count,
        )


class AuctionPricingUpdate(PricingModeFields):
    """Boshlanmagan (SCHEDULED) auksionning narx rejimini to'liq almashtirish.

    To'liq almashtirish (PUT semantikasi): berilmagan maydon tozalanadi — eski rejimdan
    "osilib qolgan" qadam yoki buy-now narxi yangi rejimga o'tib ketmasin.
    reserve_price: o'suvchida — maxfiy rezerv; pasayuvchida — pastki chegara (majburiy).
    """

    reserve_price: TiyinAmount | None = Field(default=None, gt=0)
    buy_now_price: TiyinAmount | None = Field(default=None, gt=0)


class AuctionRelist(PricingModeFields):
    """Sotilmagan lotni qayta joylash: yangi narx va muddat bilan yangi auksion."""

    duration_days: Literal[3, 5, 7]
    starting_price: TiyinAmount = Field(gt=0)
    minimum_bid_increment: TiyinAmount = Field(default=TIYIN_PER_SOUM, gt=0)
    reserve_price: TiyinAmount | None = Field(default=None, gt=0)
    buy_now_price: TiyinAmount | None = Field(default=None, gt=0)


class AuctionStatusUpdate(BaseModel):
    # Sotuvchi qo'lda faqat bekor qila oladi (cancelled). ENDED/RESERVE_NOT_MET
    # faqat close oqimi orqali. Batafsil: app/services/auction_state.py
    status: AuctionStatus = Field(description="Sotuvchi so'raydigan holat (amalda: cancelled)")
