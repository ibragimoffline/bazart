# Bazart — loyihaning to'liq tavsifi

> Boshidan oxirigacha: nima qurildi, qanday ishlaydi, nima bajarildi, nima qoldi.
> Holat sanasi: **2026-09-06**. Manba — kod (`app/`, `frontend/`, `tests/`, `alembic/`),
> git tarixi (54 kommit) va `docs/`.
>
> **Faza E (2026-10).** Bazart to'lovsiz kelishuv modeliga o'tmoqda: escrow, topshirish kodi va
> nizolar (§8, §9) E1 da olib tashlanadi, order E2 da kelishuv (deal) bilan almashadi, reserve narx
> E4 da yo'qoladi. Bu hujjat o'tishdan oldingi holatni tasvirlaydi; joriy reja va holat —
> `docs/FAZA_E_BAJARISH_TARTIBI.md`, maqsadli model — `docs/DEALS.md`. Telefon narx ko'rsatkichi
> (migratsiya 0028) olib tashlangan.

---

## 1. Loyiha haqida

**Bazart** — O'zbekiston uchun C2C **muddatli auksion** marketplace.

**Muammo.** OLX va shunga o'xshash e'lonlar taxtalarida tovar oylab sotilmaydi: deadline yo'q,
narx muzlab qoladi, sotuvchi ham xaridor ham qaror qabul qilmaydi. Savdo cho'zilib ketadi,
ikkala tomon ham "keyin" deb kutadi.

**Yechim.** Har e'londa **majburiy deadline** (3 / 5 / 7 kun) + **auksion mexanikasi** +
**escrow** (pul PSP'da bloklanadi, tovar topshirilgach ozod qilinadi). Vaqt cheklovi
qarorni majburlaydi, auksion narxni bozor belgilashiga qo'yadi, escrow ikkala tomonni himoya qiladi.

**Pozitsiya qarorlari:**
- Jonli video savdo **YO'Q** — pozitsiyaga zid, xarajat va moderatsiya yuki katta.
- Escrow pulini **o'zimiz ushlamaymiz** — litsenziya yo'q. PSP hold/capture qiladi,
  biz faqat orkestratsiya qilamiz.
- Mikroservis emas, **modular monolith** — MVP tezligi va tranzaksiya butunligi.

---

## 2. Muhim qarorlar (o'zgarmaydi)

| Qaror | Sabab |
|---|---|
| Modular monolith, mikroservis EMAS | MVP tezligi, tranzaksiya butunligi |
| PostgreSQL 16 asosiy DB | Pul = ACID |
| Escrow'ni o'zimiz ushlamaymiz | Litsenziya yo'q; PSP hold/capture qiladi |
| Pul = butun son (tiyin), BIGINT | Float TAQIQ. API'da pul — string, tiyinda: `{"amount": "6200050"}` |
| Barcha vaqt UTC | Ko'rsatishda `Asia/Tashkent` |
| Jonli video YO'Q | Pozitsiyaga zid, moderatsiya yuki |
| Anti-sniping | <2 daqiqa qolganda bid → end_time +2 daqiqa (limit bilan) |
| Proxy bidding (max-bid) | `high_bidder_max` HECH QACHON API'da oshkor bo'lmaydi |
| Bid atomik | `SELECT ... FOR UPDATE` majburiy |
| Idempotentlik | Har to'lov va bid operatsiyasi `idempotency_key` bilan |
| Holat faqat state machine orqali | Qo'lda `status = ...` TAQIQ (auction / order / payment) |
| Karta PAN hech qachon saqlanmaydi | Faqat PSP token (`token_reference`) |
| PSP webhook imzosiz qabul qilinmaydi | Soxta "to'landi" = tovar bepul ketadi |
| Buyer premium 8% | BPS = 800 |
| Auto-complete 72 soat | Xaridor sukut saqlasa — order yopiladi |

---

## 3. Texnologiyalar

### Backend
Python 3.12 · **FastAPI** · **SQLAlchemy 2.0** (`Mapped` / `mapped_column`) · **Alembic** ·
**PostgreSQL 16** · **Pydantic v2** + pydantic-settings · PyJWT · bcrypt · **Celery** (Redis broker) ·
**Redis** · httpx · Pillow · pytest · ruff · uvicorn.

### Infratuzilma
Docker Compose: `api`, `worker` (Celery), `beat` (Celery beat), `db` (Postgres 16),
`redis`, `minio` (S3-mos). GitHub Actions CI: `ruff check` + `ruff format --check` + `pytest`
(Postgres + Redis servislari bilan).

### Frontend
**Next.js 16** (App Router) · TypeScript · **Tailwind CSS v4** (CSS-first `@theme`,
`tailwind.config.js` YO'Q) · **shadcn/ui** (radix base) · **lucide-react** (yagona ikonka manbasi) ·
zustand (auth store) · react-hook-form + zod · sonner (toast) · motion · `next/font/google`
(Inter — matn, Space Grotesk — sarlavha).

---

## 4. Arxitektura

### Qatlamlar

```
HTTP / WebSocket
      ↓
api/v1/endpoints/   — validatsiya, DI, HTTP status. Biznes mantiq YO'Q.
      ↓
services/           — biznes qoidalar, tranzaksiya chegarasi, state machine
      ↓
repositories/       — DB kirish (select / insert / FOR UPDATE)
      ↓
models/             — SQLAlchemy 2.0 mapping
```

**Yo'nalish qat'iy: api → services → repositories → models.** Teskari import TAQIQ.
Biznes mantiq endpoint ichida yozilmaydi.

### Papka strukturasi

```
app/
  main.py                 # create_app(), lifespan, CORS, RequestId middleware, /uploads mount
  money/                  # tiyin arifmetikasi + TiyinAmount — pul bo'yicha YAGONA manba
  core/                   # config, security (JWT/bcrypt), dependencies (DI), rate_limit,
                          # token_store, redis_client, celery_app, webhook, logging_config,
                          # request_context, request_meta
  db/                     # session.py (engine, get_db), base.py (metadata import)
  models/                 # 22 SQLAlchemy modeli + enums.py
  schemas/                # Pydantic v2 I/O sxemalari
  api/v1/router.py        # + endpoints/: 20 modul, 90 endpoint
  repositories/           # 18 repozitoriy
  services/               # 30+ servis (biznes mantiq)
  realtime/manager.py     # WebSocket ConnectionManager
  tasks/                  # Celery vazifalari (scheduled, notifications, email, dispatch)
alembic/versions/         # 19 migratsiya
tests/                    # 66 fayl, 448 test
scripts/                  # create_superadmin.py, seed_regions.py
frontend/                 # Next.js 16 ilovasi (23 sahifa, 68 komponent)
docs/                     # ARCHITECTURE, DOMAIN, AUCTION_ENGINE, PAYMENTS, DESIGN, ROADMAP
```

---

## 5. Ma'lumot modeli

### Jadvallar (22 model)

| Jadval | Vazifasi | Muhim maydonlar |
|---|---|---|
| `users` | Foydalanuvchi | email, hashed_password, role, seller_rating, phone_verified_at, telegram_chat_id, preferred_language, deleted_at |
| `categories` | Kategoriya daraxti | parent_id, slug (unique) |
| `items` | E'lon | seller_id, title, description, condition, status, images (JSON), region_id, district_id, year, equipment, defects, video_url, search_text, view_count, starting_price, reserve_price |
| `item_images` | Yuklangan rasmlar | item_id, image_url, is_primary |
| `auctions` | Auksion | item_id (unique), start/end_time, duration_days, extension_count, status, starting/current_price, minimum_bid_increment, reserve_price, highest_bidder_id, **high_bidder_max**, winner_id, winning_bid_id, original_end_time, closed_at, bid_count, unique_bidder_count, buy_now_price, second_chance_offered_at/expires_at |
| `bids` | Taklif | auction_id, bidder_id, amount, **max_amount**, is_proxy, ip (INET), device_id, user_agent, idempotency_key, status, retracted_by_id, retract_reason |
| `auction_extensions` | Anti-sniping jurnali | auction_id, old_end_time, new_end_time, triggered_by_bid_id |
| `orders` | Buyurtma | auction_id (unique), item_id, buyer_id, seller_id, final_price, status, auto_complete_at |
| `payments` | To'lov / escrow | order_id, buyer_id, amount, premium, total, currency, status, provider, provider_payment_id, **idempotency_key** (partial unique), held_at, released_at, failed_reason |
| `payment_methods` | Karta tokeni | provider, label, **token_reference** (PAN emas), is_default |
| `handovers` | Tovar topshirish | order_id (unique), method, **code** (yashirin), status, meet_address, confirmed_at |
| `disputes` | Nizo | order_id, payment_id, opened_by, reason, status, resolution, resolved_by, resolved_at |
| `reviews` | Ikki tomonlama sharh | order_id, from_id, to_id, stars (1..5), text |
| `complaints` | Shikoyat | reporter_id, target_type, target_id, reason, status, resolved_by_id |
| `notifications` | In-app xabarnoma | user_id, type, title, body, payload (JSONB), is_read, read_at |
| `conversations` / `messages` | Xaridor ↔ sotuvchi chat | buyer_id, seller_id, item_id / conversation_id, sender_id, body, is_read |
| `watchlists` | Kuzatuv ro'yxati | user_id, auction_id |
| `regions` / `districts` | O'zbekiston hududlari | name_uz, name_ru, code (unique) |
| `legal_consents` | Huquqiy roziliklar | user_id, document_type, **version**, accepted_at, ip |
| `otp_codes` | SMS OTP | phone, **code_hash** (xom kod EMAS), purpose, attempts, expires_at, consumed_at, ip |
| `audit_log` | O'zgarmas jurnal (INSERT only) | actor_id, action, entity_type, entity_id, old_value/new_value (JSONB), idempotency_key, ip (INET) |
| `webhook_events` | PSP webhook dedup | provider + event_id (unique), payload, received_at, processed_at |

### Enum'lar (`app/models/enums.py`)

- `ItemCondition`: new · used · refurbished
- `ItemStatus`: draft · scheduled · pending · active · sold · cancelled
- `AuctionStatus`: scheduled · active · ended · cancelled · **reserve_not_met**
- `BidStatus`: valid · outbid · cancelled · **retracted** · **invalidated**
- `UserRole`: user · seller · admin · **superadmin** (+ `ADMIN_ROLES`, `is_admin()` — yagona manba;
  `role == ADMIN` deb yozish superadminni jimgina chetlab o'tadi)
- `PaymentStatus`: pending · processing · paid · failed · refunded · **held** · **released** · **cancelled_hold**
- `OrderStatus`: pending_payment · paid · pickup_pending · completed · cancelled
- `HandoverMethod` / `HandoverStatus`, `DisputeReason` / `DisputeStatus`,
  `NotificationType` (outbid, won, sold, payment, handover, dispute, second_chance, ending_soon),
  `ComplaintTargetType` / `ComplaintStatus`, `ConsentDocumentType` (terms, privacy,
  auction_rules, public_offer), `OtpPurpose` (phone_verify, login, password_reset)

---

## 6. Pul tizimi (`app/money/`)

Pul bo'yicha **yagona manba**. Qoida: pul har doim **butun son, tiyinda** (`Tiyin = int`),
DB'da `BIGINT`. `float` va `Decimal` hisob-kitobda **TAQIQ**.

**`money.py`:**
- `soum_to_tiyin()` — `float` berilsa `TypeError` (62 000.50 float'da aniq emas, bir tiyin
  jimgina yo'qoladi). Tiyindan mayda qiymat rad etiladi.
- `tiyin_to_soum()`, `format_soum()` — faqat **ko'rsatish** uchun.
- `calc_buyer_premium(price, bps=800)` — **yaxlitlash FAQAT shu yerda**. Butun bo'linma
  (pastga, foydalanuvchi foydasiga). Boshqa joyda takrorlansa jami ≠ qismlar yig'indisi.
- `calc_total()`, `calc_seller_payout()` (MVP: sotuvchi komissiyasi 0%).
- `_assert_tiyin()` — `bool` ham `int`, lekin pul emas → alohida rad etiladi.

**`fields.py` — `TiyinAmount`:** API chegarasidagi shartnoma. JSON'da pul **har doim string**,
qiymat tiyinda: `{"amount": "6200050"}` = 62 000.50 so'm.
- Nega string? JS'da `number` = IEEE-754 double; 2^53 dan katta butun son jimgina buziladi.
- Nega tiyin? So'mda kasr paydo bo'ladi → mijoz float'ga o'girib aniqlik yo'qotadi.
- Texnik nozik joy: `before` validator + `handler(int)` sxemasi ishlatilgan (plain validator
  EMAS) — aks holda `Field(gt=0)` jimgina e'tiborsiz qolib manfiy narx o'tib ketardi.

---

## 7. Auksion dvigateli

### 7.1 Atomik bid (`bid_service.place_bid`)

Butun oqim **bitta tranzaksiyada**:
1. `AuctionRepository.get_for_update()` — auksion qatorini `SELECT ... FOR UPDATE` bilan qulflab qayta o'qish
2. Validatsiya **qulf ostida** (o'qilgan narx eskirmaydi)
3. Yozish + denormalizatsiya (`bid_count`, `unique_bidder_count`)
4. Bitta commit

Qulf o'rnatilgach oraliq commit qilinmaydi — har commit qulfni bo'shatadi va
"o'qi → tekshir → yoz" oynasi qayta ochiladi. `scheduled → active` avto-aktivatsiya ham
shu sababli commit'siz (`_activate_if_started_locked`). Xatoda darhol `rollback` —
kutayotgan bidlar navbatda keraksiz turmasin.

**Idempotentlik:** `idempotency_key` berilsa va shu bidder shu kalit bilan allaqachon bid
yozgan bo'lsa — yangi bid yaratilmaydi, mavjudi qaytariladi (tarmoq qayta urinishi ikki
marta bid qo'ymasin). Tekshiruv qulfdan **oldin** — takroriy so'rov butun tranzaksiyani ochmaydi.

**Isbot:** `test_bid_concurrency.py` — 12 parallel bid, alohida DB ulanishlari → aynan bitta
g'olib. Qulf olib tashlansa test yiqiladi.

### 7.2 Validatsiya qoidalari

- **Shill taqiqi:** sotuvchi o'z lotiga bid qo'yolmaydi.
- **Min qadam:** `amount >= current_price + effective_min_increment`.
- Auksion `ACTIVE` va muddati o'tmagan bo'lishi shart.
- **Typo ogohlantirishi:** joriy narxdan 3× katta bid → `high_bid_warning` bayrog'i
  (bloklamaydi, frontend tasdiq oynasi uchun).

### 7.3 Dinamik (darajali) minimal qadam (`bid_increment.py`)

Bitta qat'iy qadam past narxda juda sekin, yuqori narxda kulgili. Jadval (so'mda):

| Joriy narx | Minimal qadam |
|---|---|
| < 100 000 | 5 000 |
| 100 000 – 500 000 | 10 000 |
| 500 000 – 2 000 000 | 25 000 |
| 2 000 000 – 10 000 000 | 100 000 |
| > 10 000 000 | 250 000 |

Amaldagi qadam = `max(sotuvchi qadami, jadval qadami)` — sotuvchi faqat **yuqoriroq** qadam
qo'ya oladi, auksionni sekinlashtira olmaydi. Test muhitida jadval o'chiriladi (mavjud
kichik-summali test korpusi buzilmasin), mantiq alohida testda tekshiriladi.

### 7.4 Proxy bidding (max-bid)

- `max_amount` berilmasa — oddiy bid: ko'ringan narx = `amount`.
- `max_amount` berilsa — keyingi raqib kelganda tizim leader nomidan avtomatik bir qadam
  yuqoriga ko'taradi (leader `max`igacha), `is_proxy=True` yozuvi bilan.
- **`high_bidder_max` va `max_amount` HECH QACHON API javobida oshkor bo'lmaydi** —
  maxfiylik qalqoni, alohida test bilan qo'riqlanadi.
- Teng max'da tie-break — vaqt bo'yicha (birinchi kelgan yutadi).

### 7.5 Anti-sniping (soft close)

- `SOFT_CLOSE_WINDOW_SECONDS = 120`: tugashiga <2 daqiqa qolganda kelgan bid
  `end_time` ni **+2 daqiqa** suradi (`SOFT_CLOSE_EXTENSION_SECONDS = 120`).
- **Cheksiz cho'zilish bloklangan:** `max_soft_close_extensions = 10`. Undan keyin oxirgi
  soniyadagi bid muddatni surmaydi.
- Har uzaytirish `auction_extensions` jadvaliga yoziladi (eski/yangi muddat, qaysi bid sababli).

### 7.6 State machine (`auction_state.py`)

Ruxsat etilgan o'tishlar jadvali; qo'lda `status = ...` TAQIQ. `close` / `activate` / `cancel` —
hammasi `assert_transition()` orqali. Sotuvchi `PATCH /auctions/{id}/status` orqali faqat
**bekor qila oladi**, boshqa o'tishlar rad etiladi.

Xuddi shu naqsh: `order_state.py` (order), `payment_state.py` (escrow).

### 7.7 Bid retraction va invalidation

- **Retraction** — foydalanuvchi o'z bidini qaytarib oladi (typo). Cheklov: **joriy yetakchi
  qaytarib ololmaydi** (narxni buzib ketmasin). Bid `RETRACTED` bo'ladi, audit'da qoladi.
- **Invalidation** — admin bidni bekor qiladi (shill / firibgarlik). Bid `INVALIDATED`,
  joriy narx `_recompute_current_price()` bilan qayta hisoblanadi.

### 7.8 Yopilish oqimi (`auction_service.close_auction`)

Qator `FOR UPDATE` bilan qulflanadi (yopish paytida parallel bid g'olibni o'zgartira olmasin).
Faqat `ACTIVE` auksion yopiladi; qayta yopish 409.

1. **Bid yo'q** → `ENDED`, g'olib yo'q, item `CANCELLED`.
2. **Reserve bajarilmadi** → `RESERVE_NOT_MET` + sotuvchiga **second-chance** taklifi
   (24 soat, `SECOND_CHANCE_TTL`) + `SECOND_CHANCE` bildirishnomasi.
3. **Normal** → `ENDED`, item `SOLD`, **order yaratiladi**, g'olibga `WON` va sotuvchiga
   `SOLD` bildirishnomasi — hammasi bitta tranzaksiyada.

**Second-chance qabul qilish** (`accept_second_chance`): sotuvchi 24 soat ichida rozi bo'lsa
auksion `ENDED` bo'ladi, eng yuqori VALID bidder g'olib, order yaratiladi. Muddat o'tgan
bo'lsa 409.

### 7.9 Closer worker (`auction_closer.py`)

`end_time` o'tgan auksionlarni avtomatik yopadi. Ikki yo'l:
- **In-process**: FastAPI lifespan'dagi oddiy asyncio loop (APScheduler emas).
  Default **o'chiq** (`auction_closer_enabled=False`) — testlarda fon vazifasi bazani buzmasin.
- **Celery beat** (prod): `close_due_auctions_task`, `auction_closer_interval_seconds`.

**Idempotentlik testi:** 2 parallel yopish → aynan bitta order (`test_closer_idempotency.py`).

### 7.10 Indekslar

`ix_bids_auction_amount_created (auction_id, amount, created_at)` — eng yuqori bidni topish
uchun kompozit index, `test_bid_index.py` qalqoni bilan.

---

## 8. Escrow va to'lovlar

> **[E1] olib tashlanadi.** Bazart to'lovda ishtirok etmaydi; arxiv: `docs/archive/PAYMENTS.md`.

### 8.1 PSP abstraksiyasi (`payment_providers.py`)

`BasePaymentProvider` (ABC) shartnomasi: `create_payment`, `confirm_payment`,
**`create_hold`**, **`capture`**, **`release`**.

Implementatsiyalar:
- `MockPaymentProvider` — **faqat local/test** (`allow_mock_payments`). Prod/staging'da
  mock oqimi 404 beradi: mock doim PAID qaytargani uchun istalgan xaridor tovarni
  to'lovsiz olardi.
- `FakeFailingProvider` — xato yo'llarini sinash uchun.
- `HttpEscrowProvider` — real PSP HTTP adapteri (HMAC imzo, `Idempotency-Key`, timeout,
  status mapping). `psp_base_url` bo'sh bo'lsa adapter o'chiq; "psp" so'ralsa-yu base_url
  bo'sh bo'lsa — **aniq config xatosi** (jimgina Mock'ga qaytish YO'Q).

### 8.2 Hold oqimi (`create_hold`)

- **Summa serverdan hisoblanadi**: `order.final_price + buyer_premium(8%)`. Klientdan olinmaydi.
- **Idempotent**: bir xil `idempotency_key` bilan takroriy so'rov yangi hold yaratmaydi.
  - Begona kalitli payment oshkor bo'lmaydi (IDOR himoyasi) → 409.
  - `FAILED` bo'lgan urinish uchun yangi kalit talab qilinadi.
  - Parallel bir xil kalit → `IntegrityError` → mavjud natijaga qaytish yoki 409.
- Muvaffaqiyatda: payment `HELD`, order `PICKUP_PENDING`,
  `auto_complete_at = now + 72 soat`, audit `PAYMENT_HELD`.
- Xatoda: payment `FAILED` + sabab yoziladi (dalil qoladi), audit `PAYMENT_FAILED`, 502.

### 8.3 Capture va release

**`capture_payment`** — pul sotuvchiga o'tadi, order `COMPLETED`.
Xaridor tasdiqlaganda yoki auto-complete worker tomonidan (`actor=None`). Qator
`FOR UPDATE` bilan qulflanadi — parallel capture/release poygasi PSP'da ikki settlement bermaydi.
Idempotent: allaqachon `RELEASED` bo'lsa qayta capture qilmaydi.

**`release_hold`** — blok bekor qilinadi, pul xaridorda qoladi, order `CANCELLED`.
**FAQAT admin** (nizo qarori) yoki tizim chaqira oladi. **Xaridor o'zi release qila OLMAYDI** —
aks holda tovarni olgach hold'ni bekor qilib pulni qaytarib olardi (code review'ning
KRITIK topilmasi).

### 8.4 Webhook (`core/webhook.py` + `webhook_service.py`)

- **HMAC imzo tekshiruvi** xom bayt ustida, `compare_digest` bilan. Imzosiz/noto'g'ri → **401**.
- **Replay himoyasi**: `is_fresh(event_timestamp, max_age=300s)`.
- **Dedup**: `webhook_events` jadvalida `provider + event_id` unique.
- `reconcile_from_webhook()` — PSP = haqiqat manbai. Metod webhook tranzaksiyasi **ichida**
  chaqiriladi va **commit qilmaydi** (WebhookService bir marta commit qiladi) — hodisa yozuvi
  va payment o'zgarishi atomik bo'lishi uchun.
- Prod'da default `PSP_WEBHOOK_SECRET` bilan ilova **ko'tarilmaydi**.

### 8.5 Audit log (`audit_service.py`)

INSERT-only jurnal. Har pul harakati yoziladi: `PAYMENT_HELD`, `PAYMENT_RELEASED`,
`PAYMENT_CANCELLED_HOLD`, `PAYMENT_FAILED` — aktor, eski/yangi qiymat (JSONB),
`idempotency_key`, IP.

### 8.6 Auto-complete (`auto_complete.py`)

Xaridor 72 soat sukut saqlasa (`auto_complete_hours`) order avtomatik capture qilinadi.
**Ochiq nizoli order yakunlanmaydi** — dispute `OPEN`/`UNDER_REVIEW` bo'lsa worker o'tkazib
yuboradi. In-process poller (default o'chiq) yoki Celery beat orqali.

---

## 9. Order, topshirish, nizo

> **[E1/E2] almashadi.** Topshirish kodi va nizolar E1 da olib tashlanadi; order E2 da
> kelishuvga aylanadi (sotuvchi "Sotildi" + xaridor tasdig'i, 72 soat avto-tasdiq, sabab bilan
> bekor qilish) — `docs/DEALS.md`.

### Order (`order_service.py`, `order_state.py`)
Auksion yopilganda avtomatik yaratiladi (`auction_id` unique — ikki marta yaratilmaydi).
Holat o'tishlari state machine orqali. Ko'rish: buyer / seller / admin ro'yxatlari,
har resursda egalik tekshiruvi (IDOR).

### Handover (`handover_service.py`)
Tovar topshirish **kod bilan tasdiqlash** orqali:
1. Sotuvchi handover yaratadi (`local_meetup` yoki `delivery`), tizim **kod** generatsiya qiladi.
2. Kod **faqat kerakli tomonga** ko'rinadi (`is_code_visible()` — javob sxemasida filtrlanadi).
3. Xaridor kodni kiritib tasdiqlaydi → handover `COMPLETED` → **capture** ishga tushadi.

### Dispute (`dispute_service.py`)
- Xaridor nizo ochadi (`not_received`, `not_as_described`, `damaged`, `fake`, `other`).
- Ochiq nizo **auto-complete'ni to'xtatadi**.
- Admin hal qiladi: `RESOLVED_BUYER` → release (pul xaridorga qaytadi) yoki
  `RESOLVED_SELLER` → capture. Qaror qabul qilishda payment qatori qulflanadi.

---

## 10. Foydalanuvchi va autentifikatsiya

### JWT (`core/security.py`)
bcrypt parol hash · HS256 · access token (30 daq) · refresh token (14 kun) ·
parol tiklash tokeni (30 daq) · email tasdiqlash tokeni (60 daq). Har token `type` bilan
belgilangan — refresh tokenni access sifatida ishlatib bo'lmaydi.
Refresh token — HttpOnly cookie'da, har ishlatilganda almashtiriladi (rotation + replay
detection, `auth_sessions` jadvali). Batafsil: `docs/AUTH.md`.

### Token bekor qilish (`core/token_store.py`)
`TokenRevocationStore` abstraksiyasi: `InMemoryTokenStore` (default) yoki `RedisTokenStore`
(TTL bilan). Redis yo'q bo'lsa **graceful fallback** — ilova yiqilmaydi.

### Rollar va DI (`core/dependencies.py`)
`CurrentUser` · `CurrentActiveUser` · `CurrentAdminUser` · `CurrentSuperadminUser` ·
`require_roles(...)`. Superadmin — adminning **ustki to'plami**; tekshiruv `is_admin()` orqali.
Rol berish (`PATCH /admin/users/{id}/role`) **faqat superadminga** ochiq; admin adminni
bloklay olmaydi (`_guard_privileged_target`).

Birinchi superadmin ro'yxatdan o'tish orqali olinmaydi — `scripts/create_superadmin.py` bilan
server yonida qo'lda yaratiladi.

### Google orqali kirish (`google_identity.py`, `POST /auth/google`)
- Frontend Google Identity Services'dan ID token (`credential`) oladi, backend uni
  Google JWKS bilan tekshiradi: RS256 imzo, `aud == GOOGLE_CLIENT_ID`, `iss`, `exp`.
- Qidirish tartibi: `google_sub` → tasdiqlangan email bo'yicha bog'lash → yangi akkaunt
  (`is_verified=True`). Google emailni tasdiqlamagan bo'lsa bog'lash/yaratish rad etiladi.
- Tasdiqlanmagan mavjud akkauntga bog'lashda eski parol bekor qilinadi (pre-hijack himoyasi).
- `GOOGLE_CLIENT_ID` / `NEXT_PUBLIC_GOOGLE_CLIENT_ID` bo'sh bo'lsa — endpoint 503, tugma yashirin.

### OTP / telefon tasdiqlash (`otp_service.py`)
- Kod **hash bilan** saqlanadi (`code_hash`), xom kod DB'da yo'q.
- TTL 5 daqiqa · uzunlik 6 · 5 noto'g'ri urinishdan keyin bloklanadi.
- Cooldown 1 SMS / 60 soniya · kunlik limit: 5 / telefon, 20 / IP.
- SMS provayder abstraksiyasi: `LogSmsProvider` (local/test — kod log'ga), real provayder
  (Eskiz va h.k.) keyin ulanadi.

### Rate limiting (`core/rate_limit.py`)
Redis fixed-window, zaxira in-memory. Scope'lar: `login` (5/daq), `bid` (10/daq),
`auth` (register / forgot-password / reset-password). Mijoz IP'si `X-Forwarded-For`ning
**birinchi** qiymatidan olinadi.

---

## 11. Bildirishnomalar

### In-app (`notification_service.py`)
`notifications` jadvali. Eventlarga ulangan: **OUTBID** (stavkangiz oshib ketdi),
**WON**, **SOLD**, **SECOND_CHANCE**. Payload JSONB'da (auction_id, narx, muddat).
API: ro'yxat, o'qilmaganlar soni, bittasini / hammasini o'qilgan deb belgilash.

### Telegram (`telegram_provider.py`)
O'zbekiston uchun **asosiy kanal** (push o'rnida): `HttpTelegramProvider` (Bot API) yoki
`LogTelegramProvider`. Foydalanuvchi `POST /users/me/telegram` bilan chat'ini bog'laydi.
Token bo'sh / `telegram_enabled=False` bo'lsa yetkazish log provayderga tushadi — **graceful**.

### Push (`push_provider.py`)
`BasePushProvider` abstraksiyasi (PSP naqshi bo'yicha): `LogPushProvider`, `NullPushProvider`.
Real FCM/APNs uchun interfeys tayyor.

### Celery navbati (`tasks/notifications.py`, `tasks/email.py`)
`deliver_push`, `deliver_telegram`, `send_email` — so'rov oqimidan chiqarilgan,
foydalanuvchi kutmaydi. `tasks/dispatch.py` — eager/queue rejimini birlashtiruvchi qatlam.

---

## 12. Anti-fraud, shikoyat, huquqiy rozilik

### Anti-fraud (`fraud_service.py`)
Signal tahlili (admin endpoint `GET /fraud/signals/{user_id}`):
- **bir device / IP ostida ko'p akkaunt** (`bids.ip`, `bids.device_id` bo'yicha),
- **shill overlap** — foydalanuvchi o'z auksionlarida qatnashuvchi hisoblar bilan kesishuvi,
- **velocity** — qisqa oynada tez-tez bid (rapid bid max),
- bid soni, alohida auksionlar soni, **risk flag**lar.

### Shikoyatlar (`complaint_service.py`)
Foydalanuvchi item / user / auction / message / order ustidan shikoyat qiladi.
Admin: `OPEN → REVIEWING → RESOLVED | REJECTED`.

### Huquqiy rozilik (`legal_consent_service.py`)
Har qabul **versiya bilan** yoziladi (terms, privacy, auction_rules, public_offer) + IP.
Nizo chiqqanda "qaysi versiyadagi shartnoma qabul qilingan" savoliga javob beradi.
Stavka = ofertani qabul qilish.

---

## 13. Real-time (WebSocket)

- Kanal: `GET /api/v1/ws/auctions/{auction_id}?token=<JWT>`.
- **Auth majburiy**: access JWT `token` query parametrida (WS handshake'da Authorization
  sarlavhasi brauzer API'sida mumkin emas). Yaroqsiz token → **4401** bilan yopiladi,
  anonim ulanish room'ga **umuman qo'shilmaydi**. Handshake avval `accept` qilinadi,
  aks holda close kodi mijozga yetib bormaydi.
- `ConnectionManager` (`app/realtime/manager.py`) — auksion room'lariga fan-out.
- **Avto-broadcast**: bid muvaffaqiyatli commit bo'lgach `BID_PLACED` hodisasi
  kuzatuvchilarga yuboriladi (`current_price`, `highest_bidder_id`, `end_time`).
  Sync bid oqimidan async loop'ga ko'prik — `broadcast_threadsafe`, **best-effort**:
  xatosi bid'ni buzmaydi. `high_bidder_max` / `max_amount` hech qachon yuborilmaydi.

---

## 14. Qidiruv va hududlar

### Translit qidiruv (`translit.py`)
O'zbek tili lotin/kirill ikkiyoqlama: `to_latin()`, `to_cyrillic()`, `normalize_search()`.
`items.search_text` yozishda normalizatsiya qilinadi, qidiruvda ham — shu sabab
"телефон" va "telefon" bir xil natija beradi.

### Filtrlar (`GET /items`)
`q` (matn) · `category_id` · `seller_id` · `status` · `location` · `region_id` ·
`district_id` · `skip` / `limit`.

### Hududlar (`regions`)
14 hudud: 12 viloyat + Qoraqalpog'iston Respublikasi + Toshkent shahri.
`scripts/seed_regions.py` — **idempotent** (`code` bo'yicha), qayta ishga tushirish xavfsiz.
Tumanlar hozircha bo'sh — keyin to'ldiriladi.

---

## 15. Fayl yuklash (`storage_service.py`)

- **Oq ro'yxat**: `image/jpeg`, `image/png`, `image/webp`, `image/gif`.
  **SVG ataylab yo'q** — ichida `<script>` tashib stored XSS beradi; HTML ham rad.
- Kengaytma ham tekshiriladi (`.jpg .jpeg .png .webp .gif`) — `content_type` qalbakilashtirilsa ham.
- **Hajm limiti** 5 MB, oqim orqali bo'lak-bo'lak yoziladi (xotira DoS himoyasi).
  Limit oshsa yarim yozilgan fayl o'chiriladi.
- Rasm metama'lumoti tozalanadi (`_strip_image_metadata`).
- Bir e'longa maksimal 10 rasm.
- Hozir lokal disk (`uploads/`), `/uploads` static mount. MinIO/S3 ga o'tish uchun
  abstraksiya tayyor — servis va endpoint kodi o'zgarmaydi.

---

## 16. Admin panel

**Backend** (`/api/v1/admin/*`, 13 endpoint): foydalanuvchilar ro'yxati / bloklash / blokni
ochish / **rol o'zgartirish (faqat superadmin)** · e'lonlar ro'yxati / tasdiqlash / rad etish ·
auksionlar ro'yxati / bekor qilish · bidlar · orderlar · **statistika**.

**Frontend** (`/admin`): dashboard + users / items / auctions / orders jadvallari,
o'zbekcha yorliqlar bir joyda (`components/admin/labels.ts`).

---

## 17. API — to'liq ro'yxat (90 endpoint)

Barcha yo'llar `/api/v1` prefiksi bilan.

| Guruh | Endpoint'lar |
|---|---|
| **auth** (12) | `POST /auth/register` · `POST /auth/login` · `POST /auth/google` · `GET /auth/me` · `POST /auth/refresh` · `POST /auth/logout` · `POST /auth/forgot-password` · `POST /auth/reset-password` · `POST /auth/verification-token` · `POST /auth/verify-email` · OTP so'rash · OTP tasdiqlash |
| **users** (4) | `GET /users/me` · `PATCH /users/me` · `POST /users/me/telegram` · `PATCH /users/me/preferences` |
| **categories** (2) | `POST /categories` · `GET /categories` |
| **items** (6) | `POST /items` · `GET /items` (q, category, seller, status, location, region, district) · `GET /items/{id}` · `PATCH /items/{id}` · `DELETE /items/{id}` · `POST /items/{id}/images` |
| **auctions** (8) | `POST /auctions` · `GET /auctions` · `GET /auctions/{id}` · `GET /auctions/{id}/bids` · `PATCH /auctions/{id}/status` · `POST /auctions/{id}/close` · `POST /auctions/{id}/second-chance/accept` · `POST /auctions/{id}/bids` |
| **bids** (3) | bid qo'yish · `POST /bids/{id}/retract` · `POST /bids/{id}/invalidate` |
| **payments** (8) | `POST /payments/methods` · `GET /payments/methods` · `POST /payments/intents` · `POST /payments/holds` · `POST /payments/{id}/capture` · `POST /payments/{id}/release` · `POST /payments/webhooks/psp` · `GET /payments/orders/{order_id}` |
| **orders** (5) | `GET /orders/buyer` · `GET /orders/seller` · `GET /orders/admin` · `GET /orders/{id}` · `PATCH /orders/{id}/status` |
| **messages** (5) | suhbat yaratish · suhbatlar ro'yxati · suhbat tafsiloti · xabar yuborish · o'qilgan deb belgilash |
| **handovers** (3) | `POST /handovers` · `POST /handovers/{order_id}/confirm` · `GET /handovers/{order_id}` |
| **notifications** (4) | `GET /notifications` · `GET /notifications/unread-count` · bittasini o'qilgan · hammasini o'qilgan |
| **disputes** (4) | `POST /disputes` · `GET /disputes` · `GET /disputes/{id}` · `POST /disputes/{id}/resolve` |
| **fraud** (1) | `GET /fraud/signals/{user_id}` (admin) |
| **reviews** (2) | `POST /reviews` · `GET /reviews/user/{user_id}` |
| **regions** (2) | `GET /regions` · `GET /regions/{id}/districts` |
| **watchlist** (3) | qo'shish · ro'yxat · `DELETE /watchlist/{auction_id}` |
| **complaints** (3) | `POST /complaints` · `GET /complaints` · `PATCH /complaints/{id}` |
| **legal** (2) | `POST /legal/consent` · `GET /legal/consents` |
| **ws** (1) | `WS /ws/auctions/{auction_id}?token=` |
| **admin** (13) | users · block · unblock · role · items · approve · reject · auctions · cancel · bids · orders · statistics · listings |
| **health** (1) | `GET /health` |

---

## 18. Fon vazifalari

### Celery (`core/celery_app.py`, `app/tasks/`)
- Broker/backend: Redis (`effective_celery_broker` — berilmasa `redis_url`).
- **Beat** (davriy): `close_due_auctions_task`, `auto_complete_orders_task`.
- **Queue**: `deliver_push`, `deliver_telegram`, `send_email`.
- `task_acks_late=True`, `worker_max_tasks_per_child=1000`, timezone UTC.
- Test muhitida **doim inline** (`celery_eager`) — worker/broker talab qilinmaydi.
- Ishga tushirish: `celery -A app.core.celery_app worker` / `... beat`
  (compose'da `worker` va `beat` servislari).

### In-process pollerlar (`main.py` lifespan)
`auction_closer` va `auto_complete` asyncio loop'lari — **default o'chiq**,
prod'da Celery beat ishlatiladi. Testlarda ishga tushib bazani buzmasligi uchun.

---

## 19. Frontend

### Struktura
```
frontend/
  app/
    layout.tsx              # root layout, shrift o'zgaruvchilari, <html lang="uz">
    globals.css             # dizayn tokenlari — YAGONA manba
    (shop)/                 # 17 ommaviy sahifa
    admin/                  # 5 admin sahifasi
    dev/components/         # ichki komponent showcase (ishlab chiqarish sahifasi EMAS)
  components/               # 68 komponent: ui/, site/, lot/, order/, admin/, ...
  lib/api/                  # client, endpoints, types, realtime, order-flow, seller, admin, ...
  lib/format.ts             # tiyin -> so'm formatlash (uz-UZ)
```

### Sahifalar (23)
**Ommaviy:** bosh sahifa · katalog `/catalog/[category]` · lot `/lot/[id]` · sotish `/sell` ·
mening e'lonlarim `/my/listings` · buyurtmalar `/orders` va `/orders/[id]` ·
nizo ochish `/orders/[id]/dispute` · sharh `/orders/[id]/review` · nizolar `/disputes` ·
xabarlar `/messages` va `/messages/[id]` · bildirishnomalar `/notifications` ·
profil `/profile` · ommaviy profil `/users/[id]` · kirish `/login` · ro'yxatdan o'tish `/register`.
**Admin:** dashboard · users · items · auctions · orders.

### Dizayn tizimi (majburiy qoidalar)
1. **Emoji TAQIQ** — na UI matnida, na kod kommentlarida. Ikonka faqat `lucide-react`.
2. **"AI-generated" shablonlar TAQIQ**: krem+serif+terrakota; qora fon + neon aksent;
   gradient matn/tugma; glassmorphism; `01/02/03` markerlar; Lorem ipsum.
3. **Rang tizimi**: neytral asos (`#F7F6F4` fon, `#1B1A18` matn) + **bitta** brend aksenti —
   **majolika ko'ki `#12659E`** + semantik ranglar (`--success #0E7A46`, `--warning #E1900B`,
   `--error #C4362C`). Hardcode rang TAQIQ — faqat token.
   *Nega ko'k:* marketplace fotolari iliq va to'yingan; sovuq ko'k orqaga chekinadi va
   tovar rasmi bilan raqobatlashmaydi. Ildizi — Samarqand/Buxoro koshin an'anasi.
4. **Tipografika**: `font-heading` (Space Grotesk) + `font-sans` (Inter).
   Type scale FAQAT 12/14/16/18/24/32/48px. Spacing 4px asosida.
   **oʻ/gʻ (U+02BB) qamrovi tekshirilgan** — Manrope, Plus Jakarta Sans, Sora, Figtree, Onest
   bu belgini qamramaydi va tofu ko'rsatadi → rad etildi.
5. **Har komponent 4 holatga ega**: hover · focus-visible · disabled · loading.
   Klaviatura fokusi ko'rinadigan bo'lishi shart.
6. **Motion**: faqat 150–250ms funksional o'tishlar. Dekorativ scroll/parallax TAQIQ.
   `prefers-reduced-motion` hurmat qilinadi.
7. **Responsive 360–1440px** — mobil teng huquqli maqsad, keyin moslashtiriladigan qo'shimcha emas.

### Imzo element — "Muddat chizig'i" (Deadline bar)
Har tovar rasmining pastki chetiga o'rnatilgan ingichka vaqt-o'lchagich + tabular countdown.
Deadline yaqinlashgani sari kuchayadi: **>24 soat** neytral → **≤6 soat** amber →
**≤30 daqiqa** qizil. Bazart'ning yagona farqi — majburiy deadline; imzo shu farqni ko'zga aylantiradi.

### API qatlami
- Pul maydonlari — **tiyin, string** (`"6200050"`), `formatTiyin()` bilan so'mga o'giriladi.
- `lib/api/realtime.ts` — auksion WS hook'i (access token URL'da emas — birinchi `AUTH` xabarida).
- `lib/api/token.ts` — access token faqat xotirada; refresh — HttpOnly cookie. `client.ts` 401 da
  jimgina yangilaydi (single-flight, tablar orasida Web Lock). Batafsil: `docs/AUTH.md`.
- `lib/item-image.ts` — tovar rasmlari uchun yagona manba (`item_images` + `images` fallback).
- `components/product/assurance-block.tsx` — **hech qanday yolg'on va'da yo'q**:
  kuryer xizmati / bepul yetkazish / qaytarish kafolati platformada mavjud emas,
  shuning uchun ko'rsatilmaydi. Faqat escrow + kod bilan tasdiqlash.

---

## 20. Xavfsizlik

### Bajarilgan himoyalar
| Himoya | Joyi |
|---|---|
| Prod'da default `SECRET_KEY` bilan ilova **ko'tarilmaydi** | `config.py` model_validator |
| Prod'da default `PSP_WEBHOOK_SECRET` bilan **ko'tarilmaydi** | `config.py` model_validator |
| Mock to'lov faqat local/test | `allow_mock_payments`, prod'da 404 |
| Noma'lum provayder nomiga jimgina Mock qaytarilmaydi | `get_payment_provider()` xato beradi |
| PAN saqlanmaydi | faqat `token_reference` |
| Webhook: HMAC imzo + replay + dedup | `core/webhook.py`, `webhook_events` |
| `high_bidder_max` / `max_amount` API'da yo'q | sxemada yo'q + alohida test |
| Xaridor o'zi hold'ni release qila olmaydi | `release_hold` faqat admin/tizim |
| Hold idempotency IDOR | begona kalitli payment oshkor bo'lmaydi |
| capture/release `FOR UPDATE` | ikki settlement yo'q |
| Forgot-password token leak yopildi | `auth_service` |
| Fayl yuklash: MIME/kengaytma oq ro'yxati + 5MB | `storage_service` (SVG/HTML rad) |
| Rate limit: login / bid / auth scope + `X-Forwarded-For` | `core/rate_limit.py` |
| Token bekor qilish (Redis-backed store) | `core/token_store.py` |
| WS auth (JWT, 4401) | `endpoints/ws.py` |
| OTP kodi hash bilan saqlanadi + limitlar | `otp_service.py` |
| Superadmin bypass yopildi (`is_admin()`) | `models/enums.py` |
| Rol berish faqat superadminga | `admin_service._guard_privileged_target` |
| IDOR: har resursda egalik tekshiruvi | barcha servislar |
| Handover kodi faqat kerakli tomonga | `is_code_visible()` |
| Audit log (INSERT only) | `audit_log` jadvali |
| Strukturaviy JSON log + `request_id` | `logging_config.py`, `request_context.py` |

### Hali ochiq
- `close_auction` manual `end_time` qattiqlashtirish (auto-closer to'g'ri; manual yo'l
  sotuvchiga erta yopishga ruxsat beradi).
- Webhook event → payment mutatsiyasi to'liq (dedup/replay yadrosi bor; qolgani real PSP kelganda).
- Push/SMS ni `notification_service.create()` ga to'liq ulash (adapter tayyor).
- Redis fan-out (ko'p instansiyali WS), `X-Forwarded-For` uchun ishonchli proxy ro'yxati.
- Real PSP adapteri (Payme / Click) + **yurist xulosasi** (tashqi bog'liq, BLOKER).

---

## 21. Testlar

**448 test, 66 fayl.** Barchasi **real Postgres 16** da ishlaydi.

### Nega SQLite emas
SQLite `FOR UPDATE`, native ENUM, BIGINT semantikasi va tranzaksiya izolyatsiyasida
Postgres'dan farq qiladi. Pul va auksion logikasini SQLite'da sinash **yolg'on ishonch** beradi:
qulf yozilmagan bo'lsa ham test yashil bo'ladi, prod'da ma'lumot buziladi.
Shu sabab SQLite butunlay olib tashlandi.

Test bazasi (`bazart_test`) avtomatik yaratiladi, har test `TRUNCATE` bilan tozalanadi.
Muhit `test`: mock to'lov ruxsat etiladi, rate limiting va darajali qadam o'chiq.

### Eng katta test fayllari
| Fayl | Test |
|---|---|
| `test_money.py` | 25 |
| `test_otp.py` | 16 |
| `test_telegram.py` | 13 |
| `test_webhook_verify.py` | 11 |
| `test_payment_security.py` | 9 |
| `test_escrow.py` · `test_disputes.py` · `test_auction_state.py` · `test_psp_http_provider.py` | 8 |
| `test_handover.py` · `test_reviews.py` · `test_search.py` · `test_push.py` · `test_bid_retraction.py` · `test_token_store.py` | 7 |

### Muhim testlar
- **`test_bid_concurrency.py`** — 12 parallel bid, alohida ulanishlar → aynan bitta g'olib.
  Qulf olib tashlansa test yiqiladi.
- **`test_closer_idempotency.py`** — 2 parallel yopish → aynan bitta order.
- **`test_migrations.py`** — toza bazada `alembic upgrade head` + BIGINT tekshiruvi + `alembic check`.
  (Testlar `create_all` ishlatadi, ya'ni ular buzuq migratsiyani TUTMAYDI — shu sabab alohida test.)
- **`test_payment_security.py`** — mock guard, provayder xatosi, IDOR, self-release.
- **`test_anti_snipe_limit.py`** — uzaytirish limiti.
- **`test_bid_index.py`** — kompozit index qalqoni.

### Holat (2026-09-06)
- `ruff check .` — **All checks passed**
- `ruff format --check .` — **251 fayl formatlangan**
- `pytest --collect-only` — **448 test yig'ildi**
- To'liq `pytest` bu tekshiruvda **ishga tushirilmadi**: Docker daemon o'chiq edi,
  testlar esa real Postgres talab qiladi (`docker compose up -d db`).

---

## 22. Migratsiyalar (19)

| № | Revision | Nima qildi |
|---|---|---|
| 1 | `202606210001` | `users` |
| 2 | `202606210002` | marketplace + auksionlar (items, categories, auctions, bids) |
| 3 | `202606210003` | modullarni kengaytirish (orders, messages, payments skeleti) |
| 4 | `202606210004` | auksion/bid qoidalarini chuqurlashtirish |
| 5 | `202606210005` | `item_images` |
| 6 | `202606210006` | `orders.final_price` |
| 7 | `202606210007` | `payments` |
| 8 | `202606210008` | xabarlar o'qilgan holati |
| 9 | `202607170009` | **pul: `Numeric(12,2)` → `BIGINT` tiyin** (9 ustun, qiymat ×100) + CHECK (narx > 0) |
| 10 | `202607170010` | proxy bidding (`high_bidder_max`, `max_amount`, `is_proxy`) |
| 11 | `202607170011` | `duration_days`, `extension_count`, `ix_bids_auction_amount_created` |
| 12 | `202607170012` | escrow: `HELD`/`RELEASED`/`CANCELLED_HOLD`, `audit_log`, `idempotency_key` |
| 13 | `202607170013` | `handovers`, `notifications` |
| 14 | `202607170014` | `disputes`, bid anti-fraud (`ip`, `device_id`) |
| 15 | `202607170015` | `reviews` |
| 16 | `202607170016` | `webhook_events`, payment tz ustunlari |
| 17 | `202607210017` | payment status enum harf registri tuzatildi |
| 18 | `202607210018` | `superadmin` roli |
| 19 | `202607260019` | **MVP gap fill**: `otp_codes`, `regions`/`districts`, `complaints`, `legal_consents`, `watchlists`, `auction_extensions`, yangi enum qiymatlari (RETRACTED, INVALIDATED, SECOND_CHANCE, ENDING_SOON), item maydonlari |

**Migratsiya qoidalari:**
- Model o'zgarsa → migratsiya majburiy, **toza bazada sinaladi**.
- Postgres ENUM'ni `create_table`/`add_column` ichida ishlatganda
  `postgresql.ENUM(..., create_type=False)` — oddiy `sa.Enum` ikkinchi marta `CREATE TYPE`
  yuborib zanjirni yiqitadi.
- Pul turini o'zgartiruvchi migratsiyada ma'lumot konvertatsiyasi (`USING (col * 100)::bigint`)
  **qo'lda yoziladi** — autogenerate buni yozmaydi, qiymat 100 baravar buziladi.

---

## 23. Bajarilgan ishlar — xronologiya

Fazalar **ketma-ket** bajarildi. Sabab: Faza C (atomik bid) Faza A'siz sinab bo'lmaydi
(SQLite `FOR UPDATE`ni indamay yutadi); Faza D (escrow) Faza B'siz — Numeric/int aralashmasi
pul hisobida xatoga olib keladi.

### Poydevor (skelet)
- [x] FastAPI + SQLAlchemy 2 + Alembic + Postgres 16
- [x] Qatlamli struktura: api → services → repositories → models
- [x] Auth: register / login / refresh / logout / password reset / email verification
- [x] Rollar va DI, kategoriya daraxti, e'lonlar + rasm yuklash
- [x] Auksion yaratish, min qadam, reserve, g'olib maydonlari
- [x] Order, xabarlar, admin moderatsiya + statistika
- [x] PSP abstraksiyasi, karta tokenizatsiya, mock guard, SECRET_KEY guard

### Faza A — Xavfsizlik va poydevor ✅
- [x] `confirm-mock` teshigi yopildi (prod'da 404)
- [x] `get_payment_provider()` noma'lum nomga xato beradi
- [x] **Testlar SQLite'dan real Postgres 16 ga ko'chirildi**
- [x] Redis + MinIO (compose + healthcheck)
- [x] Rate limiting (login, bid)
- [x] CI: ruff check + ruff format --check + pytest (Postgres+Redis bilan)
- [x] `PATCH /auctions/{id}/status` cheklandi — state machine
- [x] Strukturaviy JSON logging + `request_id` middleware

### Faza B — Pul: Numeric → BIGINT tiyin ✅
- [x] Konvensiya: barcha pul `int` tiyin, yagona manba `app/money/`
- [x] Migratsiya 202607170009: 9 ustun → BIGINT (×100) + CHECK
- [x] Modellar va sxemalar `int`ga, `TiyinAmount` (JSON'da string)
- [x] Buyer premium (BPS 800) + chegara testlari + migratsiya testi

### Faza C — Auksion dvigateli ✅
- [x] **Atomik bid** (`get_for_update`, butun oqim bitta tranzaksiyada)
- [x] **Race condition testi** — 12 parallel bid, alohida ulanishlar
- [x] **State machine** (`auction_state.py`)
- [x] **Closer worker** (asyncio loop, APScheduler emas)
- [x] `scheduled → active` avto-aktivatsiya (qulf ostida, commit'siz)
- [x] **Proxy bidding** + maxfiylik qalqoni testi
- [x] Worker idempotentligi testi
- [x] `duration_days` (3/5/7) — orqaga mos
- [x] `extension_count` limiti (anti-sniping cheksiz cho'zilmaydi)
- [x] Kompozit index `ix_bids_auction_amount_created`

### Faza D — Escrow, idempotentlik, audit ✅ (yadro)
- [x] `PaymentStatus`: HELD / RELEASED / CANCELLED_HOLD
- [x] `payments.idempotency_key` (partial unique)
- [x] `BasePaymentProvider` escrow shartnomasi + Mock
- [x] Escrow state machine + hold/capture/release oqimi
- [x] **Webhook imzo tekshiruvi** (HMAC, xom bayt, compare_digest, replay) — imzosiz 401
- [x] `audit_log` (INSERT only) + pul operatsiyalariga ulangan
- [x] Buyer premium 8%
- [x] Auto-complete 72 soat worker + `orders.auto_complete_at`
- [x] Webhook replay/dedup (`is_fresh` + `provider+event_id` unique)
- [x] Real PSP HTTP adapteri (`HttpEscrowProvider`)
- [ ] **Yurist bilan tekshirish** — hold/capture modeli litsenziya talab qiladimi (BLOKER, biznes)
- [ ] Real PSP shartnomasi (Payme/Click)

### Fazadan keyingi ishlar ✅
| Bosqich | Holat |
|---|---|
| Real-time | ✅ WebSocket + ConnectionManager + JWT auth + bid'da avto-broadcast |
| Handover | ✅ Kod bilan tasdiq oqimi, kod yashirin, tasdiq → capture |
| Bildirishnomalar | ✅ In-app + Telegram provayder + push abstraksiyasi + Celery navbati |
| Anti-fraud | ✅ Signal tahlili (device/IP, shill overlap, velocity) + admin endpoint |
| Nizolar | ✅ Dispute oqimi, auto-complete ochiq nizoda to'xtaydi |
| Observability | ✅ JSON logging + `request_id` |
| Sotuvchi reytingi | ✅ Ikki tomonlama sharh (`reviews`) + reyting qayta hisoblash |
| Bid retraction / invalidation | ✅ Foydalanuvchi qaytaradi, admin bekor qiladi + narx qayta hisoblanadi |
| Second chance | ✅ Reserve bajarilmasa sotuvchiga 24 soatlik taklif |
| OTP / telefon | ✅ Hash bilan saqlash, TTL, urinish/cooldown/kunlik limitlar |
| Hududlar | ✅ 14 hudud + idempotent seed skripti |
| Qidiruv | ✅ Lotin/kirill translit normalizatsiya |
| Watchlist | ✅ Kuzatuv ro'yxati |
| Shikoyatlar | ✅ 5 tur ob'ekt ustidan, admin oqimi |
| Huquqiy roziliklar | ✅ Versiya + IP bilan yoziladi |
| Darajali min qadam | ✅ 5 darajali jadval, sotuvchi faqat oshira oladi |
| Superadmin | ✅ Rol ierarxiyasi + `create_superadmin.py` |
| Celery | ✅ worker + beat + compose servislari |
| **Frontend** | ✅ Next.js 16, 23 sahifa, 68 komponent, dizayn tizimi, admin panel |

### Keyingi bosqichlar (hali emas)
- Mobil klient (API allaqachon shunga mo'ljallangan)
- Beta: cheklangan kategoriya + Toshkent, real pul, kichik hajm

---

## 24. Konfiguratsiya (`app/core/config.py`)

Muhim sozlamalar (`.env` orqali):

| Guruh | Sozlama | Default |
|---|---|---|
| Muhit | `ENVIRONMENT` | `local` (local · test · staging · production) |
| DB | `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5433/bazart` |
| JWT | `SECRET_KEY` · `ACCESS_TOKEN_EXPIRE_MINUTES` · `REFRESH_TOKEN_EXPIRE_DAYS` | — · 30 · 14 |
| Auksion | `SOFT_CLOSE_WINDOW_SECONDS` · `SOFT_CLOSE_EXTENSION_SECONDS` · `MAX_SOFT_CLOSE_EXTENSIONS` | 120 · 120 · 10 |
| Qadam | `TIERED_BID_INCREMENT_ENABLED` | `True` |
| Worker | `AUCTION_CLOSER_ENABLED` · `AUTO_COMPLETE_ENABLED` | `False` (prod'da beat) |
| To'lov | `BUYER_PREMIUM_BPS` · `AUTO_COMPLETE_HOURS` | 800 · 72 |
| PSP | `PSP_WEBHOOK_SECRET` · `PSP_BASE_URL` · `PSP_API_KEY` · `PSP_TIMEOUT_SECONDS` | — · "" · "" · 15.0 |
| Rate limit | `RATE_LIMIT_ENABLED` · `..._LOGIN_PER_MINUTE` · `..._BID_PER_MINUTE` | True · 5 · 10 |
| Redis | `REDIS_URL` | `redis://localhost:6379/0` |
| Celery | `CELERY_BROKER_URL` · `CELERY_TASK_ALWAYS_EAGER` · `CELERY_BEAT_ENABLED` | redis_url · False · False |
| Yuklash | `UPLOAD_MAX_BYTES` · `MAX_IMAGES_PER_ITEM` | 5 000 000 · 10 |
| Telegram | `TELEGRAM_ENABLED` · `TELEGRAM_BOT_TOKEN` | False · "" |
| OTP | `OTP_ENABLED` · `SMS_PROVIDER` · `OTP_TTL_SECONDS` · `OTP_MAX_ATTEMPTS` · kunlik limitlar | True · `log` · 300 · 5 · 5/20 |
| CORS | `CORS_ORIGINS` | `["http://localhost:3000"]` |

---

## 25. Ishga tushirish

```bash
# 1. Infratuzilma (testlardan OLDIN — testlar real Postgres talab qiladi)
docker compose up -d db redis minio

# 2. Migratsiyalar
alembic upgrade head

# 3. Hududlarni yuklash (idempotent)
python scripts/seed_regions.py

# 4. Birinchi superadmin
python scripts/create_superadmin.py --email admin@bazart.uz --password '...'

# 5. Backend
uvicorn app.main:app --reload            # http://localhost:8000

# 6. Fon vazifalari (ixtiyoriy, prod uslubi)
celery -A app.core.celery_app worker -l info
celery -A app.core.celery_app beat -l info

# 7. Frontend
cd frontend && npm run dev               # http://localhost:3000

# Butun stek bitta buyruq bilan
docker compose up --build
```

**Portlar:** Postgres host'da **5433** (5432 emas — mahalliy o'rnatilgan Postgres band
qilishi mumkin, ulanish jimgina noto'g'ri serverga tushadi), Redis 6379,
MinIO 9000 (API) / 9001 (console), API 8000, Frontend 3000.

### Tekshiruv (kommitdan oldin majburiy)
```bash
ruff check . && ruff format --check .
.venv/Scripts/python.exe -m pytest
```

---

## 26. Kod uslubi

- ruff: `line-length = 100`, `target-version = "py312"`, lint: `E, F, I, UP, B`.
- Docstring **o'zbekcha**, `"""..."""`. **Nima uchun** — muhimroq, nima — emas.
- Type hints majburiy. `Mapped[...]` / `mapped_column(...)`.
- `datetime.now(UTC)` — naive datetime TAQIQ.
- Pul: har doim `Tiyin` (butun son). `Decimal` / `float` TAQIQ.
  Hisob-kitob faqat `app/money/` orqali, sxemada `TiyinAmount`.
- Xavfsizlik yoki pul mantiqini "keyin tuzatamiz" deb qoldirmaslik — TODO + ROADMAP.

---

## 27. Hujjatlar

| Fayl | Nima haqida |
|---|---|
| `CLAUDE.md` | Loyiha qoidalari, qarorlar, ish tartibi |
| `docs/PROJECT_OVERVIEW.md` | **Shu fayl** — loyihaning to'liq tavsifi |
| `docs/ARCHITECTURE.md` | Tizim arxitekturasi, qatlamlar, oqimlar |
| `docs/DOMAIN.md` | Jadvallar, ustunlar, enum'lar |
| `docs/AUCTION_ENGINE.md` | Atomik bid, proxy bidding, anti-sniping, closer, state machine |
| `docs/PAYMENTS.md` | Escrow, PSP adapter, idempotentlik, webhook imzo, audit, huquq |
| `docs/DESIGN.md` | Frontend dizayn tizimi: palitra, shrift, layout, imzo element |
| `docs/ROADMAP.md` | Fazalar A→D va keyingilari |
| `frontend/AGENTS.md` | Next.js 16 uchun ogohlantirish (breaking changes) |

---

## 28. Raqamlarda

| Ko'rsatkich | Qiymat |
|---|---|
| Git kommitlar | 54 |
| Python fayllar (app + tests + alembic) | ~224 |
| Modellar | 22 |
| Servislar | 30+ |
| Repozitoriylar | 18 |
| API endpoint'lar | 90 |
| Alembic migratsiyalar | 19 |
| Testlar | 448 (66 fayl) + frontend Vitest 25 |
| Frontend sahifalar | 23 |
| Frontend komponentlar | 68 |
| ruff | toza (251 fayl formatlangan) |
