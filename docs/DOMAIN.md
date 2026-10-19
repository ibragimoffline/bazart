# Domen modeli

Manba: `app/models/*.py` + `alembic/versions/` (28 migratsiya, head = `202610200028`).
Bu hujjat asosan Faza A–C davridagi holatni yozadi; keyingi jadvallar (offers, pricing_mode va h.k.)
`docs/OFFERS.md`, `docs/AUCTION_ENGINE.md` va `docs/PROJECT_OVERVIEW.md` §5 da. Pul ustunlari
allaqachon BIGINT tiyin (Faza B).

> **Faza E (o'tish davri).** Bazart to'lovsiz kelishuv modeliga o'tmoqda (`docs/FAZA_E_BAJARISH_TARTIBI.md`, `docs/DEALS.md`). Quyida "[E1]"/"[E2]"/"[E4]" belgili qismlar shu bosqichlarda olib tashlanadi yoki almashtiriladi; ungacha kod ularni hali o'z ichiga oladi.

## 0. Umumiy qoidalar

- Barcha `created_at` / `updated_at` — `datetime.now(UTC)`. Ko'rsatishda `Asia/Tashkent`.
- Enum'lar Python tomonda `StrEnum`, DB tomonda nomlangan PG enum (`SqlEnum(..., name="...")`).
- PK: `int` autoincrement, `index=True`.

## 1. Pul: hozirgi holat va maqsad

| | Hozir (kod) | Maqsad |
|---|---|---|
| Tur | `Numeric(12, 2)` → Python `Decimal` | **`BigInteger`** → Python `int` |
| Birlik | so'm, 2 kasr | **tiyin** (1 so'm = 100 tiyin) |
| Chegara | 9 999 999 999.99 | ~9.2·10^18 tiyin |
| Float | Ishlatilmagan (tekshirildi) | **TAQIQ** |

**Nega:** `Numeric` xavfsiz, lekin serializatsiya/JSON/tillar orasida yaxlitlash chetlari
tug'diradi va UZS'da kasr amalda ishlatilmaydi. Butun tiyin — bir ma'noli.
**Migratsiya:** Faza B. Ta'sir qiladigan ustunlar: `items.starting_price`, `items.reserve_price`,
`auctions.starting_price`, `auctions.current_price`, `auctions.minimum_bid_increment`,
`auctions.reserve_price`, `bids.amount`, `orders.final_price`, `payments.amount`.
(`users.seller_rating` — `Numeric(3,2)`, bu pul emas, o'zgarmaydi.)

## 2. users

| Ustun | Tur | Izoh |
|---|---|---|
| id | int PK | |
| email | String(320) | unique, index |
| full_name / phone / bio / avatar_url / location | String | nullable |
| seller_rating | Numeric(3,2) | default 0 — pul emas |
| seller_rating_count | int | default 0 |
| hashed_password | String(255) | bcrypt (Google orqali yaratilganda — tasodifiy, noma'lum parol hash'i) |
| google_sub | String(255) | nullable, unique, index — Google ID token `sub` |
| is_active / is_verified | bool | default true / false |
| role | enum `user_role` | `user` \| `seller` \| `admin`, index |
| created_at / updated_at | datetime | |

Bog'lanishlar: `items`, `auctions` (seller_id), `won_auctions` (winner_id), `bids`,
`payment_methods`, `orders_as_buyer`, `orders_as_seller`.

## 3. items / item_images

| Ustun | Tur | Izoh |
|---|---|---|
| id | int PK | |
| seller_id | FK users.id | index |
| title | String(160) | index |
| description | Text | nullable |
| category_id | FK categories.id | nullable, index |
| condition | enum `item_condition` | `new` \| `used` \| `refurbished` |
| status | enum `item_status` | `draft` \| `scheduled` \| `pending` \| `active` \| `sold` \| `cancelled` |
| images | JSON | `list[str]`, eski maydon — `item_images` bilan dublikat |
| location / item_location | String(160) | ikkalasi ham bor (dublikat, tozalash kerak) |
| starting_price | Numeric(12,2) | → BIGINT tiyin |
| reserve_price | Numeric(12,2) | nullable → BIGINT tiyin |

`item_images`: `id`, `item_id` FK, `image_url` String(500), `is_primary` bool, `created_at`.

**Muammo:** `images` (JSON) va `item_images` (jadval) bir vaqtda mavjud; `location` va
`item_location` ham dublikat. Tozalash kerak.

## 4. auctions

| Ustun | Tur | Izoh |
|---|---|---|
| id | int PK | |
| item_id | FK items.id | **unique** — 1 item = 1 auksion |
| seller_id | FK users.id | index |
| start_time | DateTime(timezone=True) | |
| end_time | DateTime(timezone=True) | index — closer worker shu bo'yicha skanerlaydi |
| status | enum `auction_status` | `scheduled` \| `active` \| `ended` \| `cancelled` \| `reserve_not_met`, index |
| starting_price | Numeric(12,2) | → BIGINT tiyin |
| current_price | Numeric(12,2) | → BIGINT tiyin |
| minimum_bid_increment | Numeric(12,2) | default 1 → BIGINT tiyin |
| reserve_price | Numeric(12,2) | nullable → BIGINT tiyin |
| highest_bidder_id | FK users.id | nullable, index |
| winner_id | FK users.id | nullable, index |
| winning_bid_id | FK bids.id | `use_alter=True` (aylanma FK) |

**Maqsadli qo'shimchalar:**

| Ustun | Tur | Nega |
|---|---|---|
| `high_bidder_max` | BIGINT nullable | Proxy bidding. **API javobida HECH QACHON oshkor bo'lmaydi** |
| `duration_days` | smallint | 3/5/7 — majburiy deadline biznes qoidasi |
| `extension_count` | int default 0 | Anti-sniping cheksiz cho'zilmasligi uchun |
| `version` | int | Optimistik lock (agar FOR UPDATE yetmasa) |

## 5. bids

| Ustun | Tur | Izoh |
|---|---|---|
| id | int PK | |
| auction_id | FK auctions.id | index |
| bidder_id | FK users.id | index |
| amount | Numeric(12,2) | → BIGINT tiyin |
| status | enum `bid_status` | `valid` \| `outbid` \| `cancelled`, index |
| created_at | datetime | |

**Maqsadli:** `max_amount` (BIGINT nullable — foydalanuvchi kiritgan max, maxfiy),
`is_proxy_generated` (bool — avtomatik ko'tarilgan bid), kompozit index `(auction_id, amount DESC, created_at ASC)`.

## 6. orders

> **[E2]** `orders` jadvali `deals` bilan almashadi (holatlar `agreed`/`completed`/`cancelled`,
> keyin `fee_pending`). Quyidagi "Maqsadli" ustunlar (buyer premium, handover) endi rejada YO'Q.

| Ustun | Tur | Izoh |
|---|---|---|
| id | int PK | |
| auction_id | FK auctions.id | **unique** |
| item_id / buyer_id / seller_id | FK | index |
| final_price | Numeric(12,2) | → BIGINT tiyin |
| status | enum `order_status` | `pending_payment` \| `paid` \| `pickup_pending` \| `completed` \| `cancelled`, index |

**Maqsadli:** `buyer_premium_amount` (BIGINT — 8%, BPS 800), `total_amount` (BIGINT =
final_price + buyer_premium), `auto_complete_at` (72 soat), `handover_confirmed_at`.

## 7. payments / payment_methods

> **[E1]** To'lov jadvallari olib tashlanadi — Bazart to'lovda ishtirok etmaydi. Tarixiy
> loyiha: `docs/archive/PAYMENTS.md`.

`payment_methods`: `id`, `user_id` FK, `provider` String(80), `label`, `token_reference` String(255),
`is_default`, `created_at`.

**KRITIK:** PAN, CVV, amal muddati maydonlari YO'Q va bo'lmaydi. Faqat `token_reference` (PSP tokeni).

`payments`: `id`, `order_id` FK, `buyer_id` FK, `amount` Numeric(12,2), `currency` String(3) default `UZS`,
`status` enum `payment_status` (`pending` \| `processing` \| `paid` \| `failed` \| `refunded`),
`provider` String(80), `provider_payment_id` String(255), `created_at`, `updated_at`.

**Maqsadli (Faza D):**

| Element | Nega |
|---|---|
| `idempotency_key` String unique | Takroriy so'rov ikki marta pul yechmasligi uchun |
| PaymentStatus: `HOLD`, `RELEASED`, `CANCELLED_HOLD` | Escrow holatlari — hozir YO'Q |
| `hold_expires_at` | PSP hold muddati |
| `audit_log` jadvali | Kim, qachon, nima o'zgartirdi — pul bo'yicha majburiy |

## 8. categories / conversations / messages

`categories`: `id`, `parent_id` (self-FK), `name`, `slug` (unique), `description`, `is_active`.
`conversations`: `id`, `buyer_id`, `seller_id`, `item_id` (nullable).
`messages`: `id`, `conversation_id`, `sender_id`, `body` Text, `is_read`, `created_at`.

## 9. Migratsiyalar

| Revision | Nima |
|---|---|
| 202606210001 | users |
| 202606210002 | marketplace + auctions |
| 202606210003 | modullar kengaytmasi |
| 202606210004 | auction/bid qoidalari |
| 202606210005 | item_images |
| 202606210006 | orders.final_price |
| 202606210007 | payments |
| 202606210008 | messages read state (head) |

Model o'zgarsa migratsiya **majburiy**. `alembic revision --autogenerate -m "..."` → generatsiyani
qo'lda tekshir (enum va tur o'zgarishlarini autogenerate ko'pincha noto'g'ri chiqaradi).
