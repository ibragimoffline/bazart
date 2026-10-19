# Auksion dvigateli

> **Faza E (2026-10):** rezerv narx, `RESERVE_NOT_MET` va rezervli second chance **E4.2 da o'chadi**;
> tushuvchi narx chegarasi `floor_price` ga ko'chadi (E4.1); Dutch-fallback (§11) va rejalashtirilgan
> boshlash (§12) **E3 da o'chadi**. Quyida har bandga belgi qo'yilgan. §1–§8 sarlavhalaridagi "YO'Q"
> dastlabki holatni bildiradi — proxy bidding, closer va state machine hozir kodda BOR.
> Kelishuv modeli: `docs/DEALS.md`; bajarish tartibi: `docs/FAZA_E_BAJARISH_TARTIBI.md`.

Bu — mahsulotning yuragi. Bu yerdagi xato = noto'g'ri g'olib = ishonch yo'qolishi.
Kod: `app/services/bid_service.py`, `app/services/auction_service.py`,
`app/repositories/bid_repository.py`.

## 1. Holat: nima BOR, nima YO'Q

| Element | Holat | Joy |
|---|---|---|
| Anti-sniping (soft close) | **BOR**, ishlaydi, testi bor | `bid_service.py:86-97` |
| Shill taqiqi (sotuvchi o'z lotiga bid) | **BOR** | `bid_service.py:56-60` |
| Min qadam tekshiruvi | **BOR** | `bid_service.py:79-84` |
| Deadline tekshiruvi | **BOR** | `bid_service.py:67-77` |
| `scheduled → active` avto-aktivatsiya | **BOR** (lekin faqat bid kelganda) | `auction_service.py:49-59` |
| Reserve tekshiruvi | **BOR** | `auction_service.py:78-85` |
| **Bid atomikligi (`FOR UPDATE`)** | **YO'Q** | butun kodda `with_for_update` yo'q |
| **Proxy bidding (max-bid)** | **YO'Q** | maydon ham yo'q |
| **Avtomatik yopish (worker)** | **YO'Q** | faqat `POST /auctions/{id}/close`, sotuvchi qo'lda |
| **State machine** | **YO'Q** | `status` to'g'ridan-to'g'ri o'zlashtiriladi |
| Race condition testi | **YO'Q** | conftest SQLite → `FOR UPDATE` sinab bo'lmaydi |

## 2. Atomik bid — MAJBURIY algoritm

**Muammo (hozir):** ikki bid parallel kelsa, ikkalasi ham `current_price = 100` ni o'qiydi,
ikkalasi ham 110 qo'yadi, ikkalasi ham qabul bo'ladi. Oxirgi yozgan yutadi. Ma'lumot buziladi.

**Yechim:** auksion qatorini tranzaksiya boshida lock qilish.

```python
from sqlalchemy import select
from sqlalchemy.orm import Session


def place_bid(self, auction_id: int, bidder: User, payload: BidCreate) -> Bid:
    """Bidni atomik qabul qiladi.

    Auksion qatori FOR UPDATE bilan lock qilinadi: parallel bidlar navbatga
    turadi va har biri YANGILANGAN current_price ni ko'radi. Locksiz ikki bid
    bir xil narxni o'qib, ikkalasi ham qabul bo'lib qoladi.
    """
    # 1. LOCK — barcha o'qishlardan OLDIN. Butun tranzaksiya davomida ushlanadi.
    auction = self.db.execute(
        select(Auction).where(Auction.id == auction_id).with_for_update()
    ).scalar_one_or_none()
    if auction is None:
        raise HTTPException(404, "Auction not found")

    # 2. Validatsiya — endi lock ostida, ma'lumot ishonchli
    self._validate_bid(auction, bidder, payload)

    # 3. Yozish
    bid = Bid(auction_id=auction.id, bidder_id=bidder.id, amount=payload.amount)
    if auction.winning_bid is not None:
        auction.winning_bid.status = BidStatus.OUTBID
    auction.current_price = payload.amount
    auction.winning_bid = bid
    auction.highest_bidder_id = bidder.id

    # 4. Anti-sniping — hali lock ostida
    self._apply_soft_close_extension(auction)

    self.db.add_all([bid, auction])
    self.db.commit()  # lock shu yerda bo'shaydi
    self.db.refresh(bid)
    return bid
```

**Qoidalar:**
- Lock **birinchi** o'qishda olinadi. Avval o'qib, keyin lock qilish — foydasiz.
- Deadlock oldini olish: har doim **auction → bid** tartibida lock.
- Lock ushlab turganda tashqi chaqiruv (PSP, HTTP, email) **TAQIQ** — tranzaksiya cho'ziladi.
- `with_for_update(nowait=True)` ishlatmaslik: bid navbatga turishi kerak, xato qaytarmasligi.

## 3. Min qadam

```
step = max(minimum_bid_increment, tier_step(current_price))   # TIERED_BID_INCREMENT_ENABLED
minimum_next_bid = current_price + step
```
`amount < minimum_next_bid` → 400 (`BidService._min_step`, jadval: `services/bid_increment.py`).
Test muhitida jadval o'chiq — faqat sotuvchi qadami.

`AuctionRead.minimum_next_bid` — aynan shu qiymat API javobida (computed). Frontend qadam
jadvalini TAKRORLAMAYDI, shu maydonni ko'rsatadi.

Bid tarixi: `GET /auctions/{id}/bids` — ochiq, ism maskalangan (`bidder_display`),
`max_amount`/`high_bidder_max` sxemada yo'q.

## 4. Proxy bidding (max-bid) — YO'Q, qilinadi

Foydalanuvchi **max** kiritadi. Tizim uning nomidan faqat kerakli minimal miqdorda ko'taradi.

```python
def _resolve_proxy(auction: Auction, new_max: int, bidder_id: int) -> int:
    """Yangi max-bid kelganda ko'rinadigan narxni hisoblaydi.

    Qaytariladigan qiymat — OMMAVIY current_price. Yutqazgan tomonning maxi
    hech qachon oshkor qilinmaydi.
    """
    step = auction.minimum_bid_increment
    current_max = auction.high_bidder_max

    if current_max is None:
        return auction.starting_price  # birinchi bid: boshlang'ich narx

    if new_max > current_max:
        # Yangi bidder yutdi: eski maxdan bir qadam yuqori, lekin o'z maxidan oshmagan holda
        return min(new_max, current_max + step)

    if new_max == current_max:
        return current_max  # teng — vaqt bo'yicha birinchisi yutadi

    # Yangi bidder yutqazdi: mavjud yetakchi bir qadam ko'tariladi
    return min(current_max, new_max + step)
```

**KRITIK:** `high_bidder_max` va `bids.max_amount` **hech qachon** API javobiga
(`AuctionRead`, `BidRead`, admin ro'yxatlari, WebSocket event) qo'shilmaydi.
Oshkor bo'lsa — raqib aniq bir tiyin yuqori qo'yib har doim yutadi. Bu auksionni o'ldiradi.

## 5. Anti-sniping — BOR

`bid_service.py:86-97`:

```python
seconds_until_close = (end_time - now).total_seconds()
if 0 < seconds_until_close <= settings.soft_close_window_seconds:  # 120s
    auction.end_time = end_time + timedelta(seconds=settings.soft_close_extension_seconds)  # +120s
```

Sozlamalar: `SOFT_CLOSE_WINDOW_SECONDS=120`, `SOFT_CLOSE_EXTENSION_SECONDS=120`.

**Eslatma:** metod docstring'ida "intentionally a no-op" deyilgan — bu **eskirgan**,
kod aslida ishlaydi. Tegilganda docstring tuzatilsin.

**Kelajak:** `extension_count` limiti (masalan max 20 cho'zilish) — cheksiz cho'zilishning oldini olish.

## 6. Yopish worker — YO'Q, KRITIK

Hozir: `POST /api/v1/auctions/{id}/close`, faqat **sotuvchi** chaqiradi
(`auctions.py:77-88`). Sotuvchi chaqirmasa — auksion `active` bo'lib muzlab qoladi.
Bu mahsulotning asosiy va'dasini ("majburiy deadline") **buzadi**.

Kerakli worker:

```python
async def close_expired_auctions(db: Session) -> None:
    """end_time o'tgan aktiv auksionlarni yopadi. Har 10 soniyada ishlaydi.

    Har auksion ALOHIDA tranzaksiyada yopiladi: bittasi xato bersa qolgani yopilaveradi.
    """
    now = datetime.now(UTC)
    expired_ids = db.scalars(
        select(Auction.id)
        .where(Auction.status == AuctionStatus.ACTIVE, Auction.end_time <= now)
        .order_by(Auction.end_time)
        .limit(100)
    ).all()

    for auction_id in expired_ids:
        try:
            auction = db.execute(
                select(Auction)
                .where(Auction.id == auction_id, Auction.status == AuctionStatus.ACTIVE)
                .with_for_update(skip_locked=True)  # boshqa worker olgan bo'lsa — o'tkazib yubor
            ).scalar_one_or_none()
            if auction is None:
                continue
            # Lock ostida qayta tekshir: anti-sniping end_time ni cho'zgan bo'lishi mumkin
            if _as_utc(auction.end_time) > datetime.now(UTC):
                continue
            AuctionService(db).close_auction(auction)
        except Exception:
            db.rollback()
            logger.exception("close failed", extra={"auction_id": auction_id})
```

- `skip_locked=True` — bir nechta worker instansiyasi bir auksionni ikki marta yopmasligi uchun.
- Lock ostida `end_time` **qayta** tekshiriladi: skan bilan lock orasida anti-sniping cho'zishi mumkin.
- Idempotent: allaqachon `ended` bo'lsa — hech narsa qilmaydi.
- Runner tanlovi (ARQ / APScheduler / Celery) — **ochiq**, Faza C'da hal qilinadi.

## 7. State machine — YO'Q, qilinadi

> **E4.2 da o'chadi:** `reserve_not_met` holati va unga o'tishlar.

Ruxsat etilgan o'tishlar (`AuctionStatus`):

```
scheduled ──► active ──► ended
     │           │
     │           ├──► reserve_not_met
     │           └──► cancelled (faqat admin)
     └──► cancelled
```

**TAQIQ:** `ended → active`, `ended → ended`, `cancelled → *`, `reserve_not_met → active`.

```python
_ALLOWED: dict[AuctionStatus, frozenset[AuctionStatus]] = {
    AuctionStatus.SCHEDULED: frozenset({AuctionStatus.ACTIVE, AuctionStatus.CANCELLED}),
    AuctionStatus.ACTIVE: frozenset(
        {AuctionStatus.ENDED, AuctionStatus.RESERVE_NOT_MET, AuctionStatus.CANCELLED}
    ),
    AuctionStatus.ENDED: frozenset(),
    AuctionStatus.RESERVE_NOT_MET: frozenset(),
    AuctionStatus.CANCELLED: frozenset(),
}


def transition(auction: Auction, new: AuctionStatus) -> None:
    """Auksion holatini FAQAT shu funksiya o'zgartiradi.

    To'g'ridan-to'g'ri auction.status = ... yozish TAQIQ: bu yerda audit,
    tekshiruv va yon effektlar (order yaratish, xabarnoma) markazlashgan.
    """
    if new not in _ALLOWED[auction.status]:
        raise InvalidTransition(f"{auction.status} → {new} taqiqlangan")
    auction.status = new
```

**Muammo (hozir):** `PATCH /api/v1/auctions/{id}/status` sotuvchiga **istalgan** holatni
o'rnatishga ruxsat beradi (`auctions.py:61-74`) — hech qanday tekshiruvsiz. Sotuvchi yutqazayotgan
auksionni `cancelled` qilib qo'yishi mumkin. Bu endpoint state machine bilan qattiq cheklanishi kerak.

## 8. Majburiy testlar

| Test | Nega |
|---|---|
| Parallel 2 bid, bir xil narx → faqat bittasi yutadi | Atomiklikning yagona haqiqiy isboti |
| N=50 parallel bid → `current_price` = eng yuqorisi, bidlar soni to'g'ri | Yuk ostida yaxlitlik |
| Anti-sniping: 119s qolganda bid → `end_time` +120s | BOR (`test_bids.py`) |
| Anti-sniping: 300s qolganda bid → `end_time` o'zgarmaydi | Chegara |
| Proxy: A max=100, B max=80 → narx 85, A yetakchi | Proxy mantiq |
| Proxy: API javobida `high_bidder_max` YO'Q | Maxfiylik — regressiya qalqoni |
| Sotuvchi o'z lotiga bid → 400 | BOR |
| `end_time` o'tgan → bid 400 | BOR |
| Worker: `end_time` o'tgan auksion avtomatik `ended` | Va'da |
| Worker ikki marta ishga tushsa → bitta order | Idempotentlik |
| `ended → active` → xato | State machine |

**KRITIK:** hozir `tests/conftest.py` **SQLite in-memory** (`sqlite+pysqlite:///:memory:`) ishlatadi.
SQLite'da `FOR UPDATE` yo'q va u indamay o'tkazib yuboradi → atomiklik testi **yolg'on yashil**
beradi. Race testi yozishdan **oldin** test bazasi Postgres'ga ko'chirilishi shart (Faza A).

## 9. Buy-now, qayta joylash, "tugashiga oz qoldi" — BOR

> **E4.3:** buy-now birinchi valid bidda yopiladi; rezerv va yashirin proxy max tekshiruvi o'chadi.
> **E3.6:** qayta joylash `POST /items/{id}/relist` ga o'tadi (uch rejim, "faqat bir marta" cheklovisiz).
> **E4.2:** rezervli second chance o'chadi; second-chance mexanizmi faqat "g'olib javob bermadi"
> holatida keyingi bidderga taklif uchun qoladi (`docs/DEALS.md` §6).

**Buy-now** (`AuctionService.buy_now`, `POST /auctions/{id}/buy-now`):
- Sotuvchi auksion ochishda `buy_now_price` beradi (ixtiyoriy). Qoida (`_validate_pricing`):
  `buy_now > starting_price` va rezerv bo'lsa `buy_now >= reserve_price` — aks holda 400.
- **Option B — rezervgacha ochiq** (`buy_now_window_open`): rezerv bo'lsa, joriy narx
  rezervga yetguncha ochiq — bid tushgan bo'lsa ham; rezervsiz auksionda birinchi taklifgacha
  (Option A). `AuctionRead.buy_now_available` shu qoida bo'yicha (UI uchun).
- Qulf ostida qo'shimcha: yetakchining yashirin proxy max'i rezervni qoplagan bo'lsa (u rezerv
  narxida olishga rozi) — 409. Xabar umumiy, max oshkor bo'lmaydi.
- Mavjud bidlar: yutuvchi bid OUTBID, barcha tirik bidderlarga "lot sotildi" (OUTBID) xabari.
- Natija oddiy g'alaba bilan bir xil: buy-now narxida VALID bid yoziladi, `ACTIVE → ENDED`
  state machine orqali, order mavjud oqim bilan yaratiladi (buyer premium to'lovda). FOR UPDATE —
  ikkinchi xaridor yoki parallel bid 409 oladi. Sotuvchi o'z lotini sotib ololmaydi (400).

**Qayta joylash** (`AuctionService.relist`, `POST /auctions/{id}/relist`):
- Faqat sotilmagan lot: `ENDED` + g'olibsiz yoki `RESERVE_NOT_MET`. Boshqasi 409, begona 403.
- `auctions.item_id` UNIQUE bo'lgani uchun e'lon **nusxa ko'chiriladi** (matn, rasm yozuvlari,
  hudud) — yangi item `relisted_from_id` bilan + yangi ACTIVE auksion, bitta tranzaksiyada.
- `items.relisted_from_id` UNIQUE: bitta e'lon faqat bir marta qayta joylanadi.
- `RESERVE_NOT_MET`da ochiq second-chance **yopiladi** (`second_chance_expires_at = now`) —
  aks holda bitta tovar ikki xaridorga sotilishi mumkin edi.
- UI tavsiyasi: taklif bo'lgan bo'lsa eng yuqori taklif, bo'lmasa eski narx −10%.

**"Tugashiga oz qoldi"** (`services/ending_soon.py`):
- Tugashdan `ENDING_SOON_LEAD_MINUTES` (60) oldin kuzatuvchilar + tirik bidli foydalanuvchilarga
  (sotuvchidan tashqari) `ENDING_SOON` bildirishnoma (in-app + Telegram + push). Yetakchi va
  ortda qolganlarga matn har xil.
- Bir marta: `auctions.ending_soon_notified_at`; anti-sniping uzaytirsa ham takrorlanmaydi.
  Qatorlar `FOR UPDATE SKIP LOCKED` — beat va in-process closer bir auksionni ikki marta olmaydi.
- Ishga tushirish: closer tik'ida (in-process) va Celery beat `notify-ending-soon`
  (`ENDING_SOON_INTERVAL_SECONDS`, 60).

## 10. Pasayuvchi (golland) auksion — BOR

> **E4.1:** pastki chegara `reserve_price` dan alohida `floor_price` ustuniga ko'chadi.

`auctions.pricing_mode`: `ascending` (klassik) | `descending`. Pasayuvchida:

- **Narx vaqtdan hisoblanadi, bazada saqlanmaydi:**
  `narx = max(pastki_chegara, boshlang'ich - oraliqlar x qadam)`, bu yerda
  `oraliqlar = floor((hozir - start_time) / price_drop_interval_minutes)`.
  Pul qismi — `app/money.calc_descending_price` (butun son, yaxlitlash yo'q); vaqt qismi —
  `services/price_schedule.py`. Celery narxni tushirmaydi — worker kechiksa ham narx aniq.
- **Pastki chegara = `reserve_price`** (majburiy, boshlang'ichdan past; DB CHECK
  `ck_auctions_descending_config`). Qiymati javobda oshkor bo'lmaydi; chegaraga yetganda
  `next_price_drop_at = null` bo'ladi.
- `AuctionRead.current_price` — sotilmagan bo'lsa jonli narx (yakunlangan, sotilmaganda —
  tugash paytidagi narx); sotilgan bo'lsa — saqlangan sotuv narxi. `has_reserve=false`,
  `reserve_met=null` (chegara "qoplanadigan" rezerv emas).
- **Bid yo'q** (409). Yagona yo'l — `POST /auctions/{id}/buy-now`: auksion `FOR UPDATE` bilan
  qulflanadi, narx QULF OSTIDA shu lahzaga hisoblanadi, bid + order + `ACTIVE -> ENDED`
  bitta tranzaksiyada. Ikki xaridor bir vaqtda bossa — bittasi o'tadi, qolgani 409
  (`tests/test_descending_auction.py::test_parallel_buy_now_only_one_wins`; qulf olib
  tashlanganda 8 tadan 8 tasi "o'tib" g'olibni ustma-ust yozishi mutatsiya bilan tasdiqlangan).
- Narx faqat pasayadi — xaridor sahifada ko'rganidan ko'p to'lamaydi.
- Sotilmay tugasa — closer oddiy auksion kabi `ENDED` (g'olibsiz), qayta joylash mumkin.
- Yaratish: `pricing_mode=descending` + `price_decrement` + `price_drop_interval_minutes`
  (5..1440) + `reserve_price`; `buy_now_price` berilmaydi (422).

## 11. Gibrid model: taklifsiz auksion -> pasayuvchi bosqich — BOR

> **E3.3 da o'chadi** (yashirin avtomatik Dutch-fallback yo'q; sotuvchi o'zi qayta joylaydi).

Sotuvchi o'suvchi auksion yaratishda **oldindan rozilik** beradi:
`dutch_fallback_floor` (o'sha bosqichning eng past narxi, boshlang'ichdan past; aks holda 400).
Pasayuvchi auksionga berilmaydi (422).

- Auksion **taklifsiz** (birorta VALID bid yo'q) tugasa, `close_auction` o'sha tranzaksiyada
  (auksion qulfi ostida) e'lonni nusxalaydi (`relisted_from_id`) va 3 kunlik `DESCENDING`
  auksion ochadi: narx asl boshlang'ichdan boshlanadi, har 60 daqiqada tushadi, ~60 soatda
  chegaraga yetadi (oxirgi ~12 soat chegarada). Qadam — `app/money.calc_dutch_step`
  (yuqoriga, 1 so'mga yaxlitlanadi — yagona joy).
- Eski auksion `ENDED`, `continued_as_auction_id` -> yangi (UNIQUE). Kuzatuvchilar ko'chiriladi;
  sotuvchi va kuzatuvchilarga `DUTCH_STARTED` xabari.
- Bidli (sotilgan) yoki `RESERVE_NOT_MET` auksion o'tmaydi (u yerda second-chance oqimi).
  Davom etgan auksionning o'zida rozilik yo'q — zanjir cheksiz davom etmaydi.
- **Rozilik ommaga oshkor emas** (na chegara, na yoqilganligi): xaridorlar "taklif tushmasa
  arzonlashadi" deb bilsa, birinchi auksionda taklif bermay kutardi. Faqat sodir bo'lgach
  `continued_as_auction_id` ko'rinadi.
- Davom etgan lotni qo'lda qayta joylash — 409 (bitta tovar ikki marta joylanmaydi).

## 12. Holatga qarab standart rejim, boshlanishgacha o'zgartirish, narx jadvali — BOR

> **E3.2 da o'chadi:** `SCHEDULED`, "Keyinroq boshlash", `PATCH /auctions/{id}/pricing`.
> Narx jadvali (`price_forecast`) va holatga qarab tavsiya qoladi (E6.1 dagi tayyor tanlovlarga o'tadi).

- **Standart rejim (UI, sotish formasi):** yangi mahsulot -> pasayuvchi (tavsiya: chegara 80%,
  muddat oxiridan ~12 soat oldin chegaraga yetadigan soatlik qadam); ishlatilgan/tiklangan ->
  o'suvchi + "hoziroq sotib olish" (tavsiya 130%). Tavsiyalar faqat sotuvchi o'zi o'zgartirmagan
  maydonlarga qo'yiladi. API standarti o'zgarmagan (`pricing_mode` default `ascending`) —
  pasayuvchi rejim qadam va chegarasiz bo'lmaydi, uni server o'ylab topmaydi.
- **Boshlanishgacha o'zgartirish:** `PATCH /auctions/{id}/pricing` — faqat `SCHEDULED` va
  `start_time > now` (qulf ostida), aks holda 409. To'liq almashtirish: berilmagan maydon
  tozalanadi. Sotish formasida "Keyinroq boshlash"; "Mening mahsulotlarim"da "Narx rejimi".
- **O'z vaqtida faollashtirish (tuzatildi):** ilgari `SCHEDULED` auksion faqat birinchi bid'da
  faollashardi — buy-now uni rad etardi, closer esa yopmasdi. Endi `close_due_auctions`
  avval `activate_due_auctions` ni bajaradi (closer tik'i + Celery beat), buy-now ham qulf
  ostida dangasa faollashtiradi.
- **Narx jadvali (xaridor uchun):** `AuctionRead.price_forecast` — har to'liq kun belgisida va
  tugashda kutilayotgan narx (faqat haqiqiy pasayishlar, chegarada to'xtaydi). UI:
  "Narx 3 kundan keyin X so'mgacha tushadi". DIQQAT: prognoz chegaraga yetsa, chegara qiymati
  ko'rinadi — narx shaffofligi uchun ataylab qilingan kelishuv.

## 13. Kuzatuv xabarlari: narx tushdi, 2 soat qoldi, ortda qoldingiz — BOR

Barcha xabarlar `NotificationService.create` orqali: in-app yozuv + push (abstraksiya, hozir
`LogPushProvider` — real FCM/APNs va qurilma tokenlari YO'Q) + Telegram (bot bog'langan
foydalanuvchiga; `PUBLIC_SITE_URL` bo'lsa xabar oxirida lot/buyurtma havolasi).

- **Narx tushdi** (`services/price_alerts.py`, `PRICE_DROPPED`): faol pasayuvchi auksion
  kuzatuvchilariga (sotuvchidan tashqari). Har soatlik pasayishda EMAS: oxirgi xabardagi
  (yoki boshlang'ich) narxdan kamida `PRICE_DROP_NOTIFY_MIN_BPS` (10%) tushgach yoki chegaraga
  yetganda — bir marta. `auctions.last_price_alert`; har auksion `FOR UPDATE SKIP LOCKED`
  (xarid qilinayotgani kutilmaydi). Closer tik'i + Celery beat `price-drop-alerts` (5 daqiqa).
- **2 soat qoldi** (`ENDING_SOON`): `ENDING_SOON_LEAD_MINUTES=120`, sarlavha sozlamadan
  ("Tugashiga 2 soat qoldi"); kuzatuvchilar + tirik bidderlar, bir marta (§9).
- **Ortda qoldingiz** (`OUTBID`): bid oqimida (oddiy va proxy himoyasi) — matnda lot nomi va
  joriy narx.
- Matnlardagi narx — `app/money.format_soum_text` (butun so'mda ".00" yo'q, yaxlitlanmaydi).
