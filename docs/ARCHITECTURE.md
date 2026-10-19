# Arxitektura

## 1. Nima quriladi

Bazart — C2C muddatli marketplace. Har e'londa majburiy deadline (3/5/7 kun), narx erkin
takliflar (asosiy) yoki auksion (ixtiyoriy) orqali aniqlanadi. Savdo **kelishuv** bilan tugaydi:
Bazart to'lovda ishtirok etmaydi, tomonlarga tasdiqlangan kontaktlar ochiladi (Faza E).

> **Faza E (o'tish davri).** Bazart to'lovsiz kelishuv modeliga o'tmoqda (`docs/FAZA_E_BAJARISH_TARTIBI.md`, `docs/DEALS.md`). Quyida "[E1]"/"[E2]"/"[E4]" belgili qismlar shu bosqichlarda olib tashlanadi yoki almashtiriladi; ungacha kod ularni hali o'z ichiga oladi.

Asosiy farq OLX'dan: **e'lon muzlab qololmaydi** — deadline keladi, lot yopiladi.

## 2. Nega modular monolith

| Mikroservis | Bazart tanlovi |
|---|---|
| Bid + auksion holati alohida servislarda → distributed lock, saga | Bitta Postgres tranzaksiyasi, `SELECT FOR UPDATE` |
| Pul oqimi tarmoq orqali → eventual consistency | ACID, bitta commit |
| 5 kishilik jamoa uchun 8 ta deploy pipeline | 1 ta deploy |

Auksion dvigateli **kuchli konsistentlik** talab qiladi. Ikki bid bir vaqtda kelganda javob
"balki" bo'lolmaydi. Shuning uchun: **modular monolith**, chegaralar kod ichida (modul + qatlam),
tarmoq orqali emas. Yuk o'sganda: read-replica → o'qish, keyin kerak bo'lsa alohida modulni ajratish.

## 3. Qatlamlar

```
HTTP → app/api/v1/endpoints/*     I/O, auth DI, HTTP status. Biznes mantiq YO'Q.
           ↓
       app/services/*             Biznes qoidalar, tranzaksiya chegarasi, state o'tishlari
           ↓
       app/repositories/*         DB so'rovlari (select/insert/update)
           ↓
       app/models/*               SQLAlchemy jadval ta'riflari
```

**Qat'iy qoida:** yo'nalish faqat pastga. `repositories` → `services` importi TAQIQ.
Endpoint'dan to'g'ridan-to'g'ri `models` bilan biznes qaror qabul qilish TAQIQ.

`app/schemas/*` — Pydantic v2, chegara (HTTP) sxemalari. Model ≠ schema. Ichki maydonlar
(masalan kelajakdagi `high_bidder_max`) schema'ga chiqmaydi.

`app/core/`:
- `config.py` — `Settings` (pydantic-settings). Prod'da default SECRET_KEY bilan ko'tarilishni bloklaydi.
- `security.py` — JWT (PyJWT, HS256), bcrypt.
- `dependencies.py` — `DbSession`, `CurrentUser`, `CurrentActiveUser`, `CurrentAdmin`, `require_roles`.

`app/db/session.py` — `create_engine(settings.database_url, pool_pre_ping=True)`, `get_db()` generator.

## 4. Modullar (real)

| Modul | Endpoint prefix | Service | Holat |
|---|---|---|---|
| auth | `/api/v1/auth` | `auth_service` | Ishlaydi (register/login/refresh/reset/verify) |
| users | `/api/v1/users` | — | Ishlaydi |
| categories | `/api/v1/categories` | — | Ishlaydi (parent-child daraxt) |
| items | `/api/v1/items` | `item_service`, `storage_service` | Ishlaydi (rasm yuklash lokal disk) |
| auctions | `/api/v1/auctions` | `auction_service` | Qisman — yopish QO'LDA |
| bids | `/api/v1/bids` | `bid_service` | Qisman — atomiklik va proxy YO'Q |
| payments | `/api/v1/payments` | `payment_service`, `payment_providers` | Mock PSP — **E1 da olib tashlanadi** |
| orders | `/api/v1/orders` | `order_service` | **E2 da `deals` bilan almashadi** |
| messages | `/api/v1/messages` | `message_service` | Ishlaydi |
| admin | `/api/v1/admin` | `admin_service` | Ishlaydi (moderatsiya + statistika) |

## 5. Asosiy oqim

```
Sotuvchi: item yaratadi (draft)
   → auction yaratadi (start_time, end_time = +3/5/7 kun)
   → start_time kelganda: scheduled → active

Xaridor: POST /api/v1/bids/{auction_id}
   → validatsiya (shill? active? deadline? min qadam?)
   → auksion qatorini FOR UPDATE bilan lock
   → bid yoziladi, current_price yangilanadi, eski bid OUTBID
   → anti-sniping: <120s qolgan bo'lsa end_time += 120s

end_time keladi
   → closer (Celery beat): active → ended
   → g'olib aniqlanadi (eng yuqori VALID bid)
   → reserve bajarilmasa → reserve_not_met            [E4: reserve olib tashlanadi]
   → aks holda → Order yaratiladi (pending_payment)   [E2: → Deal (agreed), kontaktlar ochiladi]

To'lov oqimi                                        [E1: butunlay olib tashlanadi]
   → payment intent (PSP, faqat mock) → topshirish kodi → nizo

Maqsad (E2): Deal agreed
   → sotuvchi "Sotildi" + xaridor tasdiqlaydi → completed
   → "Sotildi" dan 72 soat sukut, ochiq shikoyat yo'q → avto-tasdiq
   → istalgan tomon sabab bilan bekor qiladi → cancelled
```

Batafsil: `docs/DEALS.md`.

## 6. Arxitektura teshiklari (tarixiy)

> Quyidagi jadval Faza A oldidagi holat. Hammasi yopilgan: Celery beat closer, `FOR UPDATE` +
> shartli UPDATE, Redis, testlar real Postgres'da, GitHub Actions CI.

| Teshik | Ta'sir |
|---|---|
| Background worker yo'q | Auksion o'z-o'zidan yopilmaydi. Sotuvchi `POST /close` qilmasa — lot muzlab qoladi. Bu mahsulot va'dasini buzadi |
| `with_for_update()` butun kodda yo'q | Ikki bid parallel kelsa — ikkalasi ham qabul bo'lishi mumkin |
| Redis yo'q | Rate limiting, cache, real-time fan-out uchun asos yo'q |
| Testlar SQLite'da | `FOR UPDATE` semantikasi sinalmaydi |
| CI yo'q | Regressiya faqat qo'lda ushlanadi |

## 7. Kelajakdagi tanlovlar (ochiq)

- **Background job:** Celery (Redis broker) yoki ARQ (async, yengil) yoki APScheduler (in-process).
  MVP uchun eng ehtimoliy: **ARQ yoki APScheduler**. Qaror Faza C'da qabul qilinadi.
- **Real-time:** FastAPI WebSocket (`/ws/auctions/{id}`), fan-out Redis pub/sub orqali.
  Poling MVP uchun vaqtinchalik yetarli.
- **Fayl saqlash:** hozir lokal disk (`StorageService`). Keyin S3-mos object storage.

## 8. Deploy

`Dockerfile` + `docker-compose.yml`: `api` (uvicorn) + `db` (postgres:16).
Migratsiya: `docker compose exec api alembic upgrade head`.
Prod'da: `ENVIRONMENT=production` → mock to'lovlar o'chadi, kuchsiz SECRET_KEY bloklanadi.
