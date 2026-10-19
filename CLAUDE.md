# Bazart — CLAUDE.md

C2C **muddatli** marketplace (O'zbekiston). Backend: Python 3.12 + FastAPI.

**Muammo:** OLX'da e'lonlar oylab sotilmaydi — deadline yo'q, narx muzlab qoladi.
**Yechim:** har e'londa **majburiy deadline** (3/5/7 kun) + **erkin narx takliflari** (asosiy) yoki
**auksion** (ko'tariluvchi yoki tushuvchi narx). Savdo **kelishuv** bilan tugaydi: kontaktlar
ochiladi, tomonlar o'zlari uchrashib hisob-kitob qiladi. **Bazart to'lovda ishtirok etmaydi.**

## Faza E — o'tish davri (MUHIM)

Quyidagi qoidalar **maqsadli** holatni yozadi (Faza E, `docs/ROADMAP.md`). Kod bosqichma-bosqich
yetib keladi; hali o'chirilmagan eski kod quyidagicha — **uni kengaytirma, unga yangi narsa ulama**:

| Eski kod | Qaysi bosqichda o'chadi |
|---|---|
| To'lov/escrow, `handovers`, `disputes`, `auto_complete` | E1 — **bajarildi** (migratsiya 0029) |
| `orders` (buyurtma) — `deals` (kelishuv) ga aylanadi. Oraliqda: to'lovsiz, sotuvchi `PATCH /orders/{id}/status` bilan yakunlaydi | E2 |
| `SCHEDULED` auksion, `PATCH /auctions/{id}/pricing`, "Keyinroq boshlash", Dutch-fallback | E3 |
| Rezerv narx (`RESERVE_NOT_MET`, rezervli second chance), sotuvchi qadami, `end_time` yo'li, bid retract, push abstraksiyasi, `seller` roli | E4 |

Bajarish tartibi va tekshiruvlar: `docs/FAZA_E_BAJARISH_TARTIBI.md` (ish branch'i `faza-e`, teg `pre-faza-e`).

## Muhim qarorlar (O'ZGARMAYDI)

| Qaror | Sabab |
|---|---|
| Modular monolith, mikroservis EMAS | MVP tezligi, tranzaksiya butunligi |
| PostgreSQL asosiy DB | Narx, zaxira, hamyon = ACID |
| **Bazart to'lovda ishtirok etmaydi** | Escrow, PSP hold, buyer premium, topshirish kodi va nizolar YO'Q. Xaridor va sotuvchi o'zaro hisob-kitob qiladi. Daromad faqat sotuvchidan (E5, hamyon) |
| **Kontaktlar faqat kelishuvdan keyin** | Ikkinchi tomonning tasdiqlangan telefoni va Telegram'i faqat kelishuv ishtirokchisiga va faqat `agreed`/`completed` holatda (`docs/DEALS.md`). Bid/taklif beruvchi ismi maskalangan qoladi |
| **Pul = butun son (tiyin), BIGINT** | Float **TAQIQ**. Hisob faqat `app/money/`. API'da pul — **string, tiyinda**: `{"amount": "6200050"}` = 62 000.50 so'm |
| Barcha vaqt UTC | Ko'rsatishda `Asia/Tashkent` |
| Jonli video YO'Q | Pozitsiyaga zid, xarajat + moderatsiya yuki |
| **Muddat faqat ikki rejimda** | Auksion va narx taklifi (3/5/7 kun). Tushuvchi narx — auksion yo'nalishi, alohida rejim emas |
| **Taklifli savdo — asosiy rejim** (`docs/OFFERS.md`) | Sotuvchi mo'ljal narx (DONA uchun) + miqdor beradi; xaridor istalgan musbat narx va miqdor taklif qiladi. Min qadam / "oldingidan yuqori" / avtomatik rad **YO'Q**. Sotuvchi qabul qiladi, rad etadi yoki qarshi taklif beradi |
| Narx dona uchun | `unit_price` saqlanadi; jami = `calc_line_total(unit, qty)` (`app/money`) |
| Zaxira atomik | Qabul: item `FOR UPDATE` + shartli `UPDATE ... WHERE quantity_available >= q` (`take_stock`). CHECK constraint lost update'ni USHLAMAYDI |
| Auksion — faqat 1 dona | Quyidagi auksion qoidalari faqat `listing_type = auction` e'lonlarga |
| **Rezerv narx YO'Q** | Ko'tariluvchi auksionda maxfiy minimal narx yo'q (E4.2). Tushuvchi narxning pastki chegarasi — alohida `floor_price` (E4.1; hozircha `reserve_price` ustunida) |
| Tushuvchi narx (`pricing_mode=descending`) | Narx BAZADA SAQLANMAYDI — vaqtdan hisoblanadi (`calc_descending_price` + `price_schedule`); bid yo'q, xarid qulf ostida joriy narxda (`docs/AUCTION_ENGINE.md` §10) |
| Sotilmay qolsa — sotuvchi qaror qiladi | Olib tashlaydi yoki auksion / narx taklifi bilan qayta joylaydi. Yashirin avtomatik Dutch-fallback YO'Q (E3.3) |
| Sotuvchi istalgan paytda olib tashlay oladi | Bid yoki ochiq takliflar bo'lsa ham (bidderlarga xabar, sotuvchi hisoblagichi oshadi). Ochiq kelishuv bo'lsa — bloklanadi (E3.5) |
| Anti-sniping (auksion) | <2 daqiqa qolganda bid → end_time +2 daqiqa |
| Proxy bidding (max-bid, auksion) | `high_bidder_max` **HECH QACHON** API'da oshkor bo'lmaydi |
| Bid va xarid atomik | `SELECT ... FOR UPDATE` majburiy (parallel testlar bilan isbotlangan) |
| Holatlar faqat state machine orqali | Auksion, taklif, kelishuv: qo'lda `status = ...` **TAQIQ** |
| **Kelishuv avto-tasdig'i 72 soat** | Sotuvchi "Sotildi" belgilagan, xaridor 72 soat jim — kelishuv `completed`. Ochiq shikoyat bo'lsa to'xtaydi |
| Yutgan xaridor javob bermasa | 48 soatlik bog'lanish oynasi, keyin sotuvchi bekor qiladi: keyingi bidderga 24 soatlik taklif yoki qayta joylash |
| Bekor qilish chegarasi | 30 kunda 3 bekor qilish → 14 kun bid va taklif taqiqi (sozlamada) |
| Idempotentlik (hamyon) | Har hamyon yozuvi (E5) `idempotency_key` bilan (UNIQUE): bir kelishuv uchun komissiya ikki marta yechilmaydi |
| Provayder webhook imzosiz qabul qilinmaydi | Hamyon to'ldirish (E5.4): soxta "to'landi" = bepul balans. `core/webhook.py` + `webhook_events` (takrorlanishdan himoya) saqlanadi |

## Tech stack (REAL)

FastAPI · SQLAlchemy 2.0 (Mapped/mapped_column) · Alembic · PostgreSQL 16 · Pydantic v2 +
pydantic-settings · PyJWT · bcrypt · pytest · ruff · uvicorn · Docker Compose (db + redis + minio) ·
GitHub Actions CI (ruff check + ruff format --check + pytest).

**Redis (ULANGAN):** token blacklist (`core/token_store.py`), rate limiting
(`core/rate_limit.py` — Redis fixed-window, zaxira: in-memory), Celery broker/backend.
Hammasida **graceful fallback** — Redis yo'q bo'lsa ilova yiqilmaydi (`core/redis_client.py`).
**Celery (ULANGAN):** `core/celery_app.py` + `app/tasks/` — beat (auksion yopish, "2 soat qoldi",
"narx tushdi", taklif muddati) va queue (Telegram, push, email). Worker:
`celery -A app.core.celery_app worker`; beat: `... beat` (compose'da `worker` + `beat` servislari).
`app/tasks/__init__.py` barcha modellarni yuklaydi (`app.db.base`) — worker mapper'lari shunga tayanadi.
`CELERY_TASK_ALWAYS_EAGER`/test'da inline bajariladi. In-process pollerlar (lifespan) default o'chiq;
E4.7 da olib tashlanadi — prod'da faqat beat.
**MinIO:** S3-mos; hozir fayllar `uploads/` ga lokal yoziladi.

## Struktura (REAL)

```
app/
  main.py              # create_app(), /api/v1 router, /uploads static mount
  money/               # tiyin arifmetikasi + TiyinAmount (pul bo'yicha YAGONA manba)
  core/                # config, security (JWT/bcrypt), dependencies, rate_limit, webhook, celery_app
  db/                  # session.py (engine, get_db), base.py (barcha modellar importi)
  models/              # user, item, auction, bid, offer, order, watchlist, notification, message, ...
  schemas/             # Pydantic v2 I/O
  api/v1/router.py     # + endpoints/: auth, users, items, offers, auctions, bids, orders, watchlist,
                       #   notifications, messages, complaints, admin, ws, ...
  repositories/        # DB kirish (select/insert)
  services/            # biznes mantiq: offer_service, bid_service, auction_service, price_schedule, ...
  tasks/               # Celery: scheduled (beat), notifications, email, dispatch
alembic/versions/      # 29 migratsiya
tests/                 # 56 fayl, 349 test
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
    (shop)/            # do'kon sahifalari: bosh sahifa, catalog, item/[id], lot/[id], sell, offers, orders, my/...
    admin/             # admin panel
    globals.css        # dizayn tokenlari — YAGONA manba (rang/o'lcham/motion)
  components/          # ui/ (shadcn primitivlari), lot/, offer/, seller/, site/, ...
  lib/                 # api/ (backend klienti, turlar), catalog.ts, format.ts, utils.ts (cn)
  components.json      # shadcn konfiguratsiyasi (aliases, baseColor=neutral)
```

**Komandalar** (`frontend/` ichida): `npm run dev` · `npm run build` · `npm run lint` ·
yangi komponent: `npx shadcn@latest add <nom>`. Dev server ishlab turganda `npm run build`
qilma — ikkalasi bitta `.next` papkasini ishlatadi va dev server buziladi.

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

1. **Bid va xarid atomik** — auksion qatori `with_for_update()` bilan qulflanadi (`get_for_update`).
   Parallel bid (`test_bid_concurrency`), parallel buy-now (`test_descending_auction`) va parallel
   taklif qabuli (`test_offers`) testlari alohida ulanishlarda — **har bosqichdan keyin o'zgarishsiz
   yashil** bo'lishi shart.
2. **Sotuvchi o'z lotiga bid qo'yolmaydi va o'z e'loniga taklif berolmaydi** (shill).
3. **Min qadam (faqat ko'tariluvchi auksion):** `amount >= current_price + qadam`; qadam — pog'onali
   platforma qadami (E4.4 dan keyin sotuvchi qadami yo'q). Taklifli e'londa min qadam YO'Q.
4. **Anti-sniping** — `SOFT_CLOSE_WINDOW_SECONDS=120`, `SOFT_CLOSE_EXTENSION_SECONDS=120`, ko'pi 10 marta.
5. **Prod'da default SECRET_KEY bilan ko'tarilish bloklangan** — `config.py` model_validator.
6. **Taklifli savdo** (`offer_service.py`): bitta xaridor — bitta ochiq taklif (partial unique index);
   faqat navbatdagi tomon (`awaiting`) qabul/qarshi taklif qiladi; javobsiz taklif 48 soatda yopiladi.
   Qulf tartibi: avval item, keyin offer. Kelishuv bekor bo'lsa donalar zaxiraga qaytadi.
7. **Kelishuvning yagona kirish nuqtasi** `DealService.create_deal(...)` (E2.4): taklif qabuli,
   auksion g'olibi, buy-now va tushuvchi narxda xarid — hammasi shu orqali (E5 komissiyasi shunga ulanadi).

## Komandalar

```bash
docker compose up -d db redis minio       # testlardan OLDIN — testlar real Postgres talab qiladi
.venv/Scripts/python.exe -m pytest        # 349 test (~9 daqiqa)
.venv/Scripts/python.exe -m pytest tests/test_bids.py
ruff check . && ruff format --check .     # CI shu ikkalasini tekshiradi
alembic upgrade head                      # toza bazada
alembic check                             # modellar va migratsiyalar mos
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
  Yaxlitlash faqat `app/money/` ichida (`calc_dutch_step`; E5 da `calc_seller_fee`);
  boshqa joyda takrorlanmaydi.

## Test qoidalari

- Testlar **real Postgres 16** da ishlaydi (`docker compose up -d db`, host port **5433**).
  SQLite'ga QAYTMA: u `FOR UPDATE`, native ENUM va izolyatsiyada Postgres'dan farq qiladi —
  qulf yozilmagan bo'lsa ham test yashil bo'lib, yolg'on ishonch beradi.
- Test bazasi (`*_test`) avtomatik yaratiladi; sessiya boshida sxema butunlay qayta quriladi
  (`DROP SCHEMA public CASCADE` — olib tashlangan modellarning eski jadvallari qolmasin), har test
  TRUNCATE bilan tozalanadi.
- Har pul, narx, zaxira va auksion o'zgarishi uchun test majburiy.
- Poyga testlari alohida ulanishlarda (`db_engine` + `sessionmaker`, `threading.Barrier`) yoziladi:
  `db_session` bitta sessiyani ulashadi va raqobatni ko'rsatmaydi. Qulf olib tashlanganda test
  yiqilishini (mutatsiya) bir marta tekshiring.

## Xavfsizlik

- Karta ma'lumotlari saqlanmaydi (to'lov yo'q; hamyon to'ldirish — provayder tomonida, E5.4).
- Webhook imzosiz qabul qilinmaydi (`core/webhook.py`), takrorlanishi `webhook_events` bilan to'siladi.
- `high_bidder_max` javob sxemasiga hech qachon qo'shilmaydi.
- Kontaktlar (telefon, Telegram) faqat kelishuv ishtirokchisiga, faqat `agreed`/`completed` da.
- IDOR: har resursda egalik tekshiruvi; yangi endpoint — IDOR testi bilan.
- Secret'lar `.env`da, git'ga tushmaydi.

## Ish tartibi

1. O'zgartirishdan oldin tegishli `docs/` faylni o'qi.
2. Model o'zgarsa → Alembic migratsiya majburiy. **Migratsiyani toza bazada sinab ko'r**
   (`alembic upgrade head` + `alembic check`) — testlar `create_all` ishlatadi, ya'ni ular buzuq
   migratsiyani TUTMAYDI. Postgres ENUM'ni `create_table`/`add_column` ichida ishlatganda
   `postgresql.ENUM(..., create_type=False)` yoz: oddiy `sa.Enum` ikkinchi marta
   `CREATE TYPE` yuborib zanjirni yiqitadi. Enum qiymatini o'chirib bo'lmaydi: yangi enum yaratib,
   ustunni unga o'tkaz. Har migratsiyaga `downgrade` yoziladi.
3. Pul turini o'zgartiruvchi migratsiyada ma'lumot konvertatsiyasini UNUTMA
   (`USING (col * 100)::bigint`) — autogenerate buni yozmaydi, qiymat 100 baravar buziladi.
4. Biznes qoida o'zgarsa → docs shu commit'da yangilanadi.
5. Kommitdan oldin: `ruff check .` + `ruff format --check .` + `pytest`.
6. Xavfsizlik yoki pul mantiqini "keyin tuzatamiz" deb qoldirma — TODO yozib, ROADMAP'ga kirit.

## docs/

| Fayl | Nima haqida |
|---|---|
| `docs/DEALS.md` | Kelishuv modeli (Faza E): holatlar, kontaktlar, tasdiqlash, bekor qilish, hisoblagichlar |
| `docs/OFFERS.md` | Taklifli savdo: narx/miqdor taklifi, muzokara, zaxira va poyga himoyasi, API |
| `docs/AUCTION_ENGINE.md` | Atomik bid, proxy bidding, anti-sniping, tushuvchi narx, closer, state machine |
| `docs/ROADMAP.md` | Fazalar A→E, bajarilganlar belgilangan |
| `docs/PROJECT_OVERVIEW.md` | Loyihaning to'liq tavsifi: funksiyalar, raqamlar |
| `docs/ARCHITECTURE.md` | Tizim arxitekturasi, qatlamlar, oqimlar, nega monolith |
| `docs/DOMAIN.md` | Real jadvallar, ustunlar, enum'lar, maqsadli o'zgarishlar |
| `docs/DESIGN.md` | Frontend dizayn tizimi: palitra (hex+kontrast), shrift, layout, imzo element |
| `docs/HOW_IT_WORKS.md` | To'liq jarayon (inglizcha) — **Faza E dan oldingi** holat (escrow bilan); E2 dan keyin yangilanadi |
| `docs/archive/PAYMENTS.md` | ARXIV: escrow/PSP dizayni (Faza D, qamrovdan chiqarilgan) |
| `docs/FAZA_E_BAJARISH_TARTIBI.md` | Faza E bajarish tartibi: bosqichlar, tekshiruvlar, belgilangan holat |
