# Bazart — CLAUDE.md

C2C **muddatli, taklifga asoslangan** marketplace (O'zbekiston). Backend: Python 3.12 + FastAPI.

**Muammo:** OLX'da e'lonlar oylab sotilmaydi — deadline yo'q, narx muzlab qoladi.
**Yechim:** har e'londa **majburiy deadline** (3/5/7 kun) + **erkin narx takliflari** (asosiy) yoki
**auksion** (ixtiyoriy) + **escrow**.

## Muhim qarorlar (O'ZGARMAYDI)

| Qaror | Sabab |
|---|---|
| Modular monolith, mikroservis EMAS | MVP tezligi, tranzaksiya butunligi |
| PostgreSQL asosiy DB | Pul = ACID |
| Escrow'ni O'ZIMIZ ushlamaymiz | Litsenziya yo'q. PSP hold/capture qiladi, biz orkestratsiya qilamiz |
| **Pul = butun son (tiyin), BIGINT** | Float **TAQIQ**. Bajarildi (Faza B): `app/money/`. API'da pul — **string, tiyinda**: `{"amount": "6200050"}` = 62 000.50 so'm |
| Barcha vaqt UTC | Ko'rsatishda `Asia/Tashkent` |
| Jonli video YO'Q | Pozitsiyaga zid, xarajat + moderatsiya yuki |
| **Taklifli savdo — asosiy rejim** (`docs/OFFERS.md`) | Sotuvchi mo'ljal narx (DONA uchun) + miqdor beradi; xaridor istalgan musbat narx va miqdor taklif qiladi. Min qadam / "oldingidan yuqori" / avtomatik rad **YO'Q**. Sotuvchi qabul qiladi, rad etadi yoki qarshi taklif beradi |
| Narx dona uchun | `unit_price` saqlanadi; jami = `calc_line_total(unit, qty)` (`app/money`) |
| Zaxira atomik | Qabul: item `FOR UPDATE` + shartli `UPDATE ... WHERE quantity_available >= q` (`take_stock`). CHECK constraint lost update'ni USHLAMAYDI |
| Auksion — ixtiyoriy, faqat 1 dona | Quyidagi auksion qoidalari faqat `listing_type = auction` e'lonlarga |
| Pasayuvchi auksion (`pricing_mode=descending`) | Narx BAZADA SAQLANMAYDI — vaqtdan hisoblanadi (`calc_descending_price` + `price_schedule`), pastki chegara = `reserve_price`; bid yo'q, buy-now qulf ostida joriy narxda (`docs/AUCTION_ENGINE.md` §10) |
| Gibrid: taklifsiz -> golland | Sotuvchi roziligi (`dutch_fallback_floor`) bilan taklifsiz tugagan auksion `close_auction` ichida 3 kunlik pasayuvchi auksionga o'tadi; rozilik ommaga OSHKOR EMAS (`docs/AUCTION_ENGINE.md` §11) |
| Narx rejimi boshlanishgacha | `PATCH /auctions/{id}/pricing` faqat `SCHEDULED` va boshlanmagan; standart rejim holatga qarab — faqat UI tavsiyasi (§12) |
| Anti-sniping (auksion) | <2 daqiqa qolganda bid → end_time +2 daqiqa |
| Proxy bidding (max-bid, auksion) | `high_bidder_max` **HECH QACHON** API'da oshkor bo'lmaydi |
| Bid atomik (auksion) | `SELECT ... FOR UPDATE` majburiy |
| Idempotentlik | Har to'lov operatsiyasi `idempotency_key` bilan |
| Auksion holati faqat state machine orqali | Qo'lda `status = ...` **TAQIQ** |
| Karta PAN hech qachon saqlanmaydi | Faqat PSP token |
| PSP webhook imzosiz qabul qilinmaydi | Soxta "to'landi" = tovar bepul ketadi |
| Buyer premium 8% | BPS = 800 |
| Auto-complete 72 soat | Xaridor sukut saqlasa — order yopiladi |

## Tech stack (REAL)

FastAPI · SQLAlchemy 2.0 (Mapped/mapped_column) · Alembic · PostgreSQL 16 · Pydantic v2 +
pydantic-settings · PyJWT · bcrypt · pytest · ruff · uvicorn · Docker Compose (db + redis + minio) ·
GitHub Actions CI (ruff check + ruff format --check + pytest).

**Redis (ULANGAN):** token blacklist (`core/token_store.py`), rate limiting
(`core/rate_limit.py` — Redis fixed-window, zaxira: in-memory), Celery broker/backend.
Hammasida **graceful fallback** — Redis yo'q bo'lsa ilova yiqilmaydi (`core/redis_client.py`).
**Celery (ULANGAN):** `core/celery_app.py` + `app/tasks/` — beat (auksion yopish, auto-complete)
va queue (push, email). Worker: `celery -A app.core.celery_app worker`; beat: `... beat`
(compose'da `worker` + `beat` servislari). `CELERY_TASK_ALWAYS_EAGER`/test'da inline bajariladi.
In-process pollerlar (lifespan) hamon bor, lekin default o'chiq — prod'da beat ishlatiladi.
**MinIO:** S3-mos; hozir fayllar `uploads/` ga lokal yoziladi.

## Struktura (REAL)

```
app/
  main.py              # create_app(), /api/v1 router, /uploads static mount
  money/               # tiyin arifmetikasi + TiyinAmount (pul bo'yicha YAGONA manba)
  core/                # config.py (Settings), security.py (JWT/bcrypt), dependencies.py (DI)
  db/                  # session.py (engine, get_db), base.py (metadata import)
  models/              # SQLAlchemy: user, item, auction, bid, order, payment, message, category, enums
  schemas/             # Pydantic v2 I/O
  api/v1/router.py     # + endpoints/: auth, users, categories, items, auctions, bids, payments, orders, messages, admin
  repositories/        # DB kirish (select/insert)
  services/            # biznes mantiq: bid_service, auction_service, payment_service, payment_providers, ...
alembic/versions/      # 8 migratsiya
tests/                 # 36 test, hammasi o'tadi
```

Qatlam yo'nalishi: **api → services → repositories → models**. Teskari import TAQIQ.
Biznes mantiq endpoint ichida yozilmaydi — service'ga.

## Frontend (Web) — texnologiyalar

Frontend `frontend/` papkasida, backend'dan alohida Node loyihasi.

Next.js 16 (App Router) · TypeScript · Tailwind CSS v4 (CSS-first, `@theme` — `tailwind.config.js` YO'Q) ·
shadcn/ui (radix base, `components.json`) · **lucide-react** (yagona ikonka manbasi) ·
`next/font/google` (Inter — matn, Space Grotesk — sarlavha, Geist Mono — raqam/kod).

```
frontend/
  app/
    layout.tsx         # root layout, shrift o'zgaruvchilari, <html lang="uz">
    page.tsx           # vaqtinchalik skelet (haqiqiy sahifa EMAS)
    globals.css        # dizayn tokenlari — YAGONA manba (rang/o'lcham/motion)
  components/ui/        # shadcn/ui primitivlari (button, input, card, badge, label)
  lib/utils.ts          # cn() — clsx + tailwind-merge
  components.json       # shadcn konfiguratsiyasi (aliases, baseColor=neutral)
```

**Komandalar** (`frontend/` ichida): `npm run dev` · `npm run build` · `npm run lint` ·
yangi komponent: `npx shadcn@latest add <nom>`.

## Frontend — MAJBURIY dizayn qoidalari

Bu qoidalar barcha frontend ishlariga tatbiq etiladi. Buzilishi — code review'da rad javob.

1. **Emoji TAQIQ** — na UI matnida, na tugmalarda, na bo'sh holatlarda, na kod kommentlarida.
   Ikonka kerak bo'lsa — faqat `lucide-react`.
2. **"AI-generated" ko'rinishli shablonlar TAQIQ:**
   - krem fon + serif sarlavha + terrakota aksent kombinatsiyasi;
   - qora fon + bitta neon-yashil/qizil aksent;
   - gradient matnlar, gradient tugmalar, glassmorphism, keraksiz blur;
   - har bo'limda `01/02/03` raqamli markerlar;
   - "Lorem ipsum" — barcha kontent real mahsulot nomlari, narxlar va tavsiflar bilan yoziladi.
3. **Rang tizimi — "lajuvard bloklar, siyoh tugmalar":** iliq qog'oz fon `#F4F2EE`, oq sirt,
   siyoh matn `#1B1A18`. Brend = **lajuvard** `#1F4E9D` (`--brand`, och fon `--brand-soft #E6EBF5`)
   — KATTA bloklarda ishlatiladi (bosh banner, kategoriya plitkalari, foto o'rni, faol tab), kichik
   tugmalarda emas. Asosiy tugmalar — **siyoh** (`--primary #1B1A18`). Semantik ranglar faqat holat
   uchun (`--success #0E7A46`, `--warning #E1900B`, `--error #C4362C`). Matn havolalari — siyoh +
   doimiy yumshoq tagchiziq. Shakllar: `--radius` 14px, tugma/chip/qidiruv `rounded-full`;
   bo'lim sarlavhalari — qalin, BOSH HARF (`SectionHeading`); mahsulot kartasi — plitka + chegarali
   teg, quti emas.
   Hammasi `app/globals.css` da CSS token sifatida e'lon qilinadi (batafsil: `docs/DESIGN.md`).
   **Komponentlarda hardcode rang TAQIQ** — faqat token orqali (`bg-primary`, `text-muted-foreground`,
   `text-success` …). warning'ga oq matn qo'yilmaydi — quyuq matn (`--warning-foreground`).
4. **Tipografika — ikki rol:** sarlavha uchun `font-heading` (Space Grotesk), matn uchun `font-sans`
   (Inter). Type scale FAQAT: **12 / 14 / 16 / 18 / 24 / 32 / 48px** (`text-xs`…`text-3xl`).
   Spacing 4px asosida (Tailwind step = `0.25rem`). Ixtiyoriy o'lcham TAQIQ.
5. **Har komponent 4 holatga ega:** `hover`, `focus-visible`, `disabled`, `loading`.
   Klaviatura fokusi **ko'rinadigan** bo'lishi shart (`:focus-visible` global ring belgilangan) —
   `outline: none` ni fokus almashtiruvisiz o'chirish TAQIQ.
6. **Motion:** faqat **150–250ms** funksional o'tishlar (hover, dropdown, modal) —
   `--duration-fast/base/slow`. Dekorativ scroll-animatsiya va parallax TAQIQ.
   `prefers-reduced-motion` hurmat qilinadi (globals.css da reset bor).
7. **Responsive:** 360px–1440px. Mobil versiya keyin moslashtiriladigan qo'shimcha EMAS —
   teng huquqli maqsad. Har layout mobil (360px) da ham sinaladi.

## Kritik biznes qoidalari

1. **Bid atomik bo'lishi shart** — `with_for_update()` bilan auksion qatorini lock qilib.
   Hozir bu YO'Q → race condition mavjud. Bid kodiga tegsang, lock qo'sh.
2. **Sotuvchi o'z lotiga bid qo'yolmaydi** (shill) — `bid_service.py:56-60`.
3. **Min qadam (faqat auksion):** `amount >= current_price + minimum_bid_increment`.
   Taklifli e'londa min qadam YO'Q — har qanday musbat dona narxi qabul qilinadi.
4. **Anti-sniping** — `SOFT_CLOSE_WINDOW_SECONDS=120`, `SOFT_CLOSE_EXTENSION_SECONDS=120`.
5. **Mock to'lov faqat local/test** — `settings.allow_mock_payments`. Prod'da mock = bepul tovar.
6. **Prod'da default SECRET_KEY bilan ko'tarilish bloklangan** — `config.py` model_validator.
7. **Taklifli savdo** (`offer_service.py`): sotuvchi o'z e'loniga taklif berolmaydi; bitta xaridor —
   bitta ochiq taklif (partial unique index); faqat navbatdagi tomon (`awaiting`) qabul/qarshi
   taklif qiladi; javobsiz taklif 48 soatda yopiladi. Qulf tartibi: avval item, keyin offer.
   Order bekor bo'lsa (`restore_stock`) donalar zaxiraga qaytadi.

## Komandalar

```bash
docker compose up -d db redis minio       # testlardan OLDIN — testlar real Postgres talab qiladi
.venv/Scripts/python.exe -m pytest        # 36 test
.venv/Scripts/python.exe -m pytest tests/test_bids.py
ruff check . && ruff format --check .     # CI shu ikkalasini tekshiradi
alembic upgrade head
alembic revision --autogenerate -m "..."
docker compose up --build                 # butun stek
uvicorn app.main:app --reload
```

**Portlar:** Postgres host'da **5433** (5432 emas — mahalliy o'rnatilgan Postgres band qilishi mumkin),
Redis 6379, MinIO 9000 (API) / 9001 (console).

## Kod uslubi

- ruff: `line-length = 100`, `target-version = "py312"`, lint: `E,F,I,UP,B`.
- Docstring (JSDoc emas), **o'zbekcha**, `"""..."""`. Nima uchun — muhimroq, nima — emas.
- Type hints majburiy. `Mapped[...]` / `mapped_column(...)` uslubi.
- `datetime.now(UTC)` — naive datetime TAQIQ.
- **Pul: har doim `Tiyin` (butun son)**. `Decimal`/`float` TAQIQ. Hisob-kitob faqat `app/money/`
  orqali. Sxemada `TiyinAmount` turi ishlatiladi (`app/money/fields.py`) — u JSON'ga string yozadi.
  Yaxlitlash faqat `app/money/` ichida (`calc_buyer_premium`, `calc_dutch_step`);
  boshqa joyda takrorlanmaydi.

## Test qoidalari

- Testlar **real Postgres 16** da ishlaydi (`docker compose up -d db`, host port **5433**).
  SQLite'ga QAYTMA: u `FOR UPDATE`, native ENUM va izolyatsiyada Postgres'dan farq qiladi —
  qulf yozilmagan bo'lsa ham test yashil bo'lib, yolg'on ishonch beradi.
- Test bazasi (`bazart_test`) avtomatik yaratiladi; har test TRUNCATE bilan tozalanadi.
- Har pul/auksion o'zgarishi uchun test majburiy.
- Race condition testi hali YO'Q — `db_session` bitta sessiyani ulashadi.
  Parallel bid testi uchun alohida ulanishlar kerak (Faza C).

## Xavfsizlik

- PAN saqlash TAQIQ. Faqat `token_reference`.
- Webhook imzosiz qabul qilinmaydi (hali webhook YO'Q).
- `high_bidder_max` javob sxemasiga hech qachon qo'shilmaydi.
- IDOR: har resursda egalik tekshiruvi (hozir toza).
- Secret'lar `.env`da, git'ga tushmaydi.

## Ish tartibi

1. O'zgartirishdan oldin tegishli `docs/` faylni o'qi.
2. Model o'zgarsa → Alembic migratsiya majburiy. **Migratsiyani toza bazada sinab ko'r**
   (`alembic upgrade head`) — testlar `create_all` ishlatadi, ya'ni ular buzuq migratsiyani
   TUTMAYDI. Postgres ENUM'ni `create_table`/`add_column` ichida ishlatganda
   `postgresql.ENUM(..., create_type=False)` yoz: oddiy `sa.Enum` ikkinchi marta
   `CREATE TYPE` yuborib zanjirni yiqitadi.
3. Pul turini o'zgartiruvchi migratsiyada ma'lumot konvertatsiyasini UNUTMA
   (`USING (col * 100)::bigint`) — autogenerate buni yozmaydi, qiymat 100 baravar buziladi.
4. Biznes qoida o'zgarsa → docs yangilanadi.
5. Kommitdan oldin: `ruff check .` + `ruff format --check .` + `pytest`.
6. Xavfsizlik yoki pul mantiqini "keyin tuzatamiz" deb qoldirma — TODO yozib, ROADMAP'ga kirit.

## docs/

| Fayl | Nima haqida |
|---|---|
| `docs/HOW_IT_WORKS.md` | To'liq jarayon (inglizcha): e'londan sotuvgacha — taklif va auksion yo'llari, order, escrow, handover, nizo, xabarlar |
| `docs/PROJECT_OVERVIEW.md` | Loyihaning to'liq tavsifi: barcha funksiyalar, bajarilgan ishlar, raqamlar |
| `docs/ARCHITECTURE.md` | Tizim arxitekturasi, qatlamlar, oqimlar, nega monolith |
| `docs/DOMAIN.md` | Real jadvallar, ustunlar, enum'lar, maqsadli o'zgarishlar |
| `docs/AUCTION_ENGINE.md` | Atomik bid, proxy bidding, anti-sniping, closer worker, state machine |
| `docs/PAYMENTS.md` | Escrow, PSP adapter, idempotentlik, webhook imzo, audit log, huquq |
| `docs/ROADMAP.md` | Fazalar A→D va keyingilari, bajarilganlar belgilangan |
| `docs/DESIGN.md` | Frontend dizayn tizimi: palitra (hex+kontrast), shrift, layout, imzo element |
| `docs/OFFERS.md` | Taklifli savdo: narx/miqdor taklifi, muzokara, zaxira va poyga himoyasi, API |
