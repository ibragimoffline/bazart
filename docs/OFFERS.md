# Taklifli savdo (offer marketplace)

Bazart'ning asosiy savdo usuli. Sotuvchi **mo'ljal narx** (bir dona uchun) va **miqdor**
beradi; xaridorlar o'z narxini va kerakli miqdorni taklif qiladi; sotuvchi har taklifni
qabul qiladi, rad etadi yoki qarshi taklif beradi. Muddatli auksion ixtiyoriy rejim bo'lib
qoladi (faqat 1 dona) — uning qoidalari `docs/AUCTION_ENGINE.md` da.

## Qoidalar

| Qoida | Qayerda |
|---|---|
| Narx DONA uchun saqlanadi; jami = `calc_line_total(unit_price, quantity)` | `app/money` |
| Har qanday musbat narx: mo'ljaldan past ham, yuqori ham. Min qadam, "oldingidan yuqori", avtomatik rad YO'Q | `OfferCreate` (faqat `> 0`) |
| Miqdor `1..quantity_available` | `OfferService._ensure_stock` |
| Sotuvchi o'z e'loniga taklif berolmaydi (400) | `make_offer` |
| Bitta xaridor — bitta ochiq taklif (409); shartni o'zgartirish — qarshi taklif yoki qaytarib olish | partial unique `uq_offers_open_per_buyer` |
| Javob navbati `awaiting`: faqat o'sha tomon qabul qiladi / qarshi taklif beradi | `_ensure_turn` |
| Sotuvchi istalgan ochiq taklifni rad eta oladi; xaridor — faqat qarshi taklifni; xaridor o'zinikini qaytarib oladi | `reject`, `withdraw` |
| Javobsiz taklif 48 soatda yopiladi (e'lon muddatidan oshmaydi) | `OFFER_TTL`, `_expiry` |
| E'londa majburiy muddat 3/5/7 kun; tugasa `EXPIRED`, qolgan zaxira bilan qayta ochiladi | `publish` |
| Auksion — faqat 1 dona va e'lon qilinmagan qoralama | `AuctionService.create_auction` |

Muddat qoidalari **har harakatda** tekshiriladi (dangasa muddat): fon vazifasi
(`expire_due` — closer tik'i va Celery beat `expire-offers`) faqat holatni tartibga
keltiradi va xabar yuboradi; to'g'rilik unga bog'liq emas.

## Holatlar

- Item: `DRAFT --publish--> ACTIVE --(zaxira 0)--> SOLD`, `ACTIVE --(muddat)--> EXPIRED --publish--> ACTIVE`,
  istalgan paytda `CANCELLED` (sotuvchi/admin; `CANCELLED` qayta ochilmaydi — moderatsiyani chetlab bo'lmaydi).
- Offer: `PENDING` -> `ACCEPTED | REJECTED | WITHDRAWN | EXPIRED`. Har harakat `offer_events` tarixida.

## Zaxira va parallel qabul qilish

Qabul qilish bitta tranzaksiyada: item `FOR UPDATE` -> offer `FOR UPDATE` -> zaxira
**shartli UPDATE** bilan ayiriladi (`take_stock`: `WHERE quantity_available >= q`) ->
order yaratiladi. Ikki qavat himoya: qulf olib tashlansa ham shartli UPDATE ortiqcha
sotuvga yo'l qo'ymaydi. DIQQAT: `CHECK (quantity_available >= 0)` lost update'ni
ushlamaydi (har tranzaksiya 3 ni o'qib 2 ni yozadi — manfiy bo'lmaydi) — bu
`tests/test_offers.py::test_parallel_accepts_never_oversell` da mutatsiya bilan tekshirilgan.

Zaxira tugasa item `SOLD`, qolgan ochiq takliflar yopiladi (`sold_out`). Order bekor
bo'lsa (hold qaytarildi, webhook, qo'lda bekor qilish) donalar zaxiraga qaytadi
(`OfferService.restore_stock`) va item kerak bo'lsa yana `ACTIVE`.

## Order va to'lov

`orders` manbai — auksion YOKI taklif (`ck_orders_single_source`). Taklif order'i:
`quantity`, `unit_price`, `final_price = quantity x unit_price`. To'lov, escrow, buyer
premium (8%), handover, nizo, sharh — o'zgarishsiz (ular `final_price` bilan ishlaydi).

## API

| Endpoint | |
|---|---|
| `POST /items` | `quantity` (default 1) |
| `POST /items/{id}/publish` `{duration_days}` | qoralamani yoki `EXPIRED` e'lonni ochadi |
| `GET /items?listing_type=offer&status=active` | katalog |
| `POST /items/{id}/offers` `{quantity, unit_price, message?}` | taklif (rate limit `bid`) |
| `GET /items/{id}/offers` | sotuvchi — hammasi; boshqalar — faqat o'ziniki |
| `GET /offers?role=buyer\|seller&status=` | mening takliflarim |
| `GET /offers/{id}` | ishtirokchi/admin, aks holda 404 |
| `POST /offers/{id}/accept\|counter\|reject\|withdraw` | muzokara |

Xaridor ismi qabul qilinguncha maskalangan (`buyer_display`).

## UI

`/item/{id}` (e'lon + taklif shakli / kelgan takliflar), `/offers` (Kelgan / Yuborilgan),
sotish formasida "Sotish usuli" (narx takliflari — default, auksion), katalog va bosh
sahifada aralash kartochkalar (`lib/catalog.ts`).
