# Yo'l xaritasi

Real holatga asoslangan. `[x]` = kodda bor va ishlaydi. `[ ]` = yo'q.

## Bajarilgan poydevor (skelet)

- [x] FastAPI + SQLAlchemy 2 + Alembic + Postgres 16 skeleti
- [x] Qatlamli struktura: api → services → repositories → models
- [x] Auth: register / login / refresh / logout / password reset / email verification (JWT + bcrypt)
- [x] Sessiyalar: refresh token HttpOnly cookie'da, rotation + replay detection (`auth_sessions`),
      30 kunlik mutlaq chegara, frontend'da jim yangilash (single-flight, Web Lock),
      WS auth birinchi xabarda — `docs/AUTH.md`
- [x] Rollar va DI: `CurrentUser`, `CurrentActiveUser`, `CurrentAdmin`, `require_roles`
- [x] Kategoriyalar (parent-child daraxt)
- [x] E'lonlar (items) + rasm yuklash (`StorageService`, lokal disk)
- [x] Auksion yaratish, min qadam, reserve, g'olib maydonlari
- [x] **Anti-sniping (soft close)** — `bid_service.py:86-97`, testi bor
- [x] **Shill taqiqi** — sotuvchi o'z lotiga bid qo'yolmaydi
- [x] Order yaratish (auksion yopilganda)
- [x] Xabarlar (buyer↔seller, faqat ishtirokchilar)
- [x] Admin moderatsiya + statistika
- [x] **PSP abstraksiyasi** (`BasePaymentProvider` ABC) + provayder registri
- [x] **Karta tokenizatsiya** — PAN saqlanmaydi (`models/payment.py:12-23`)
- [x] **Mock to'lov guard'i** — `allow_mock_payments`, prod/staging'da o'chiq
- [x] **SECRET_KEY guard** — prod'da default secret bilan ilova ko'tarilmaydi
- [x] **IDOR himoyasi** — toza
- [x] **Float ishlatilmagan** — hamma joyda Decimal
- [x] 36 test, hammasi o'tadi (`test_payment_security.py` — 8 ta xavfsizlik testi)
- [x] Docker Compose (api + db), Dockerfile, ruff konfiguratsiyasi

---

## Faza A — Xavfsizlik va poydevor

Maqsad: keyingi ishlar uchun ishonchli zamin. Busiz atomiklikni **sinab bo'lmaydi**.

- [x] `confirm-mock` teshigi yopildi — muhit guard'i (`payment_service.py`), prod'da 404
- [x] `get_payment_provider()` noma'lum nomga jimgina Mock qaytarmaydi — endi xato beradi
- [x] SECRET_KEY guard (`config.py` model_validator)
- [x] **Testlarni Postgres'ga ko'chirish** — real Postgres 16 (host port 5433), `bazart_test`
      avtomatik yaratiladi, TRUNCATE bilan tozalanadi. SQLite butunlay olib tashlandi
- [x] Redis + MinIO qo'shildi (docker-compose + healthcheck) — kod hali ULAMAGAN
- [x] Rate limiting: login (5/daq) va bid (10/daq) endpoint'lariga (`core/rate_limit.py`)
- [x] CI (GitHub Actions): `ruff check` + `ruff format --check` + `pytest` (Postgres+Redis bilan)
- [ ] Strukturaviy logging (JSON) + `request_id`
- [x] `PATCH /auctions/{id}/status` cheklandi — state machine + sotuvchi faqat bekor qila oladi

## Faza B — Pul: Numeric → BIGINT tiyin  ✅ BAJARILDI

- [x] Konvensiya: barcha pul `int` tiyin. `float` TAQIQ. Yagona manba: `app/money/`
- [x] Alembic migratsiya (202607170009): 9 ustun `Numeric(12,2)` → `BIGINT` (qiymat × 100)
      + DB CHECK (narx > 0)
- [x] Modellar va Pydantic sxemalari `int`ga (`TiyinAmount` — JSON'da string)
- [x] Buyer premium (BPS 800) + tiyin arifmetikasi `app/money/` da
- [x] Chegara testlari + migratsiya testi (toza bazada + BIGINT tekshiruvi + `alembic check`)

## Faza C — Auksion dvigateli (mahsulotning yuragi)

- [x] **Atomik bid**: `AuctionRepository.get_for_update()` — validatsiyadan oldin qulf,
      butun oqim bitta tranzaksiyada
- [x] **Race condition testi**: 12 parallel bid, alohida ulanishlar → aynan bitta g'olib.
      Isbotlangan: qulf olib tashlansa test yiqiladi (`test_bid_concurrency.py`)
- [x] **State machine** (`services/auction_state.py`): ruxsat etilgan o'tishlar jadvali,
      qo'lda `status = ...` TAQIQ. close/activate/cancel — hammasi `assert_transition` orqali
- [x] **Closer worker** (`services/auction_closer.py`): `end_time` o'tgan auksionlarni
      avtomatik yopadi, FastAPI lifespan startup'da (APScheduler EMAS — oddiy asyncio loop)
- [x] `scheduled → active` avto-aktivatsiya (bid kelganda, qulf ostida commit'siz)
- [x] **Proxy bidding** (orqaga mos): `auctions.high_bidder_max`, `bids.max_amount`,
      `bids.is_proxy` + leader avtomatik himoyasi (migratsiya 202607170010)
- [x] Test: `high_bidder_max`/`max_amount` API javobida **yo'q** (maxfiylik qalqoni)
- [x] Worker idempotentligi testi: 2 parallel yopish → aynan bitta order (`test_closer_idempotency`)
- [x] `duration_days` (3/5/7) orqali muddat — orqaga mos (end_time ham ishlaydi)
- [x] `extension_count` limiti — anti-sniping ko'pi bilan `max_soft_close_extensions` marta
- [x] Kompozit index: `ix_bids_auction_amount_created` (auction_id, amount, created_at)

**Faza C ✅ BAJARILDI.** Qolgan mayda ishlar (`duration_days` ni to'liq majburiy
qilib `end_time` yo'lini olib tashlash) frontend tayyor bo'lganda.

## Faza D — Escrow, idempotentlik, audit  (QAMROVDAN CHIQARILDI — Faza E)

> **2026-10:** Bazart to'lovda ishtirok etmaydi (Faza E qarori). Escrow, PSP, buyer premium,
> topshirish va nizolar E1 da kodda o'chiriladi. Quyidagi bandlar tarix sifatida qoldirilgan;
> ochiq bandlar endi bajarilmaydi. Saqlanadiganlar: `core/webhook.py` + `webhook_events`
> (hamyon to'ldirish, E5.4), `audit_log` (admin harakatlari).


- [ ] **Yurist bilan tekshirish**: hold/capture modeli litsenziya talab qiladimi (BLOKER, biznes)
- [x] `PaymentStatus`: `HELD` / `RELEASED` / `CANCELLED_HOLD` (migratsiya 202607170012)
- [x] `payments.idempotency_key` (partial unique) + `get_by_idempotency_key()`
- [x] `BasePaymentProvider` escrow shartnomasi: `create_hold` / `capture` / `release` + Mock
- [x] Escrow state machine (`payment_state.py`) + hold/capture/release oqimi (`payment_service.py`)
- [x] **Webhook imzo tekshiruvi** (`core/webhook.py`: HMAC, xom bayt, compare_digest, replay);
      `POST /payments/webhooks/psp` — imzosiz 401
- [x] `audit_log` jadvali (INSERT only) + pul operatsiyalariga ulangan (HELD/RELEASED/...)
- [x] Buyer premium 8% (BPS 800), `money.calc_buyer_premium` (butun bo'linma)
- [x] Auto-complete 72 soat worker (`auto_complete.py`) + `orders.auto_complete_at`
- [ ] Webhook hodisasini payment holatiga ulash (event->status, `provider_event_id` idempotent)
- [ ] Real PSP adapteri (Payme/Click) — huquqiy tekshiruvdan keyin
- [ ] Mock provayderni prod build'dan butunlay olib tashlash (real PSP kelganda)

**Faza D yadrosi kodda bor edi; Faza E da olib tashlanadi** (E1). Ochiq bandlar — qamrovdan tashqarida.

---

## Faza E — To'lovsiz kelishuv modeli va soddalashtirish  (JARAYONDA)

- [x] O'suvchi auksion `FEATURE_ASCENDING_AUCTION` bayrog'i bilan vaqtincha o'chirildi (asosiy auksion —
      pasayuvchi, asosiy sotish usuli — narx taklifi). Dvigatel saqlangan, qayta yoqish — bayroq
      (`docs/AUCTION_ENGINE.md` §14). E3/E4'dagi o'suvchiga oid soddalashtirishlar (Dutch-fallback,
      rezerv, sotuvchi qadami) bayroq yoqilganda ham kerakli bo'lib qoladi

Bajarish tartibi, tekshiruvlar va belgilangan holat: `docs/FAZA_E_BAJARISH_TARTIBI.md`.
Kelishuv modeli: `docs/DEALS.md`. Ish branch'i `faza-e`, boshlang'ich teg `pre-faza-e`.

| Bosqich | Nima | Holat |
|---|---|---|
| P | Baseline, teg, branch, hajm ro'yxati | ✅ (P.1 push — egasi qiladi) |
| E0 | Hujjatlar va qoidalar | ✅ |
| E1 | To'lov, topshirish, nizo modullarini kesish | ✅ kodda (E2 bilan bitta reliz, deploy qilinmagan) |
| E2 | Buyurtma o'rniga kelishuv: kontaktlar, tasdiqlash, bekor qilish, hisoblagichlar | [ ] |
| E3 | Mahsulot hayot sikli: `unsold`/`removed`/`rejected`, olib tashlash, qayta joylash | [ ] |
| E4 | Rezerv va soddalashtirishlar (`floor_price`, buy-now, qadam, retract, push, `seller` roli) | [ ] (E4.10 ✅) |
| E5 | Daromad: sotuvchi hamyoni, komissiya, ko'tarish (bayroq bilan, stavka 0 dan) | [ ] |
| E6 | Frontend soddalashtirish: 3 tayyor tanlov, yagona mahsulot sahifasi | [ ] |

**Reliz qoidasi:** E1 va E2 bitta relizda (oralig'ida deploy yo'q — buyurtmalar qotib qoladi).

---

## Fazadan keyin

| Bosqich | Holat |
|---|---|
| **Real-time** | ✅ WebSocket `/ws/auctions/{id}` + ConnectionManager (relay). Redis pub/sub (ko'p instansiya) va bid'da avto-broadcast — TODO |
| **Handover** | ✅ Kod bilan tasdiq oqimi (`handover_service`), kod yashirin, tasdiq -> capture |
| **Xabarnomalar** | ✅ In-app (`notification_service`), OUTBID/WON/SOLD eventlarga ulangan. SMS/push — TODO |
| **Anti-fraud** | ✅ Signal tahlili (`fraud_service`): bir device/IP ko'p akkaunt, shill overlap, velocity. `bids.ip/device_id`. Admin endpoint |
| **Auksion qulayliklari** | ✅ Buy-now (birinchi taklifgacha), sotilmagan lotni qayta joylash, "tugashiga oz qoldi" eslatmasi (`docs/AUCTION_ENGINE.md` §9) |
| **Kuzatuv xabarlari** | ✅ Narx tushdi (10%/chegara, spamsiz), 2 soat qoldi, ortda qoldingiz — in-app + Telegram (havola bilan) (`docs/AUCTION_ENGINE.md` §13). Keyin: real push (FCM/web-push, qurilma tokenlari), foydalanuvchi xabar sozlamalari |
| **Rejim standartlari va narx jadvali** | ✅ Yangi -> pasayuvchi, ishlatilgan -> o'suvchi + buy-now (UI); boshlanishgacha rejimni o'zgartirish; rejalashtirilgan auksion o'z vaqtida faollashadi; xaridor uchun kunlik narx prognozi (`docs/AUCTION_ENGINE.md` §12) |
| **Gibrid auksion** | ✅ Taklifsiz tugagan auksion sotuvchi roziligi bilan 3 kunlik pasayuvchi bosqichga o'tadi (`docs/AUCTION_ENGINE.md` §11). Keyin: roziligini e'lon qilingach o'zgartirish (hozir faqat yaratishda) |
| **Pasayuvchi auksion** | ✅ `pricing_mode=descending`: narx vaqtdan hisoblanadi (Celery'siz), pastki chegara = rezerv, atomik buy-now (`docs/AUCTION_ENGINE.md` §10). Keyin: real-time narx tushishi push (hozir sahifa pasayish vaqtida qayta yuklaydi) |
| **Taklifli savdo** | ✅ Asosiy rejim: erkin dona narxi + miqdor, qarshi taklif, 48 soatlik javob muddati, atomik zaxira (qulf + shartli UPDATE), bekor order zaxirani qaytaradi (`docs/OFFERS.md`). Auksion — ixtiyoriy, 1 dona |
| **Nizolar** | ✅ Dispute oqimi (`dispute_service`): xaridor ochadi, admin capture/release. Auto-complete ochiq nizoda to'xtaydi |
| **Observability** | ✅ Strukturaviy JSON logging + `request_id` middleware |
| Mobil | Mobil klient (API allaqachon shunga mo'ljallangan) |
| Beta | Cheklangan kategoriya + Toshkent, real pul, kichik hajm |

**Real-time / Handover / Notifications / Anti-fraud / Nizolar / Logging / Sotuvchi reytingi
/ WS auth / Push abstraksiyasi ✅ MVP darajasida.**

## Xavfsizlik backlog (code+security review'dan, hali ochiq)

- [ ] Auth: `LEGACY_REFRESH_BODY_ENABLED` ni o'chirish (eski localStorage tokenlari 14 kunda eskiradi)
- [ ] Auth: WS `?token=` query parametrini olib tashlash (yangi klient birinchi `AUTH` xabarini yuboradi)
- [ ] WS relay: mijoz yuborgan istalgan JSON room'dagi hammaga tarqatiladi — soxta `BID_PLACED`
      yuborish mumkin. Server-only broadcast'ga o'tkazish (mijoz xabarlarini rad etish)
- [ ] Auth: eskirgan/bekor qilingan `auth_sessions` qatorlarini tozalovchi beat vazifasi

Katta review'da topilib **tuzatilgan**: forgot-password token leak, capture/release
FOR UPDATE, xaridor self-release, hold idempotency IDOR, dispute decision+lock,
webhook secret prod guard, order state machine, proxy tie-break, WS auth.

**Bajarilgan (ikkinchi qattiqlashtirish to'lqini):**
- [x] Token bekor qilish -> `TokenRevocationStore` (InMemory default + Redis ixtiyoriy, ttl)
- [x] Fayl yuklash: MIME/kengaytma oq ro'yxati + 5MB limit (SVG/HTML rad)
- [x] Rate limit: register/forgot/reset "auth" scope + `X-Forwarded-For` birinchi IP
- [x] Webhook replay/dedup (`is_fresh` + `webhook_events` provider+event_id unique)
- [x] `Payment.held_at/released_at` -> timestamptz
- [x] WS avto-broadcast (sync bid -> async loop ko'prigi, best-effort)
- [x] Push provayder abstraksiyasi (LogPushProvider; real FCM/APNs interfeys tayyor)

**Hali ochiq:**
- [ ] `close_auction` manual end_time qattiqlashtirish (auto-closer to'g'ri; manual
      yo'l sotuvchiga erta yopishga ruxsat beradi — test churn sababli keyinga surildi)
- [ ] ~~Webhook event -> payment holatini yangilash~~ — Faza E: to'lov yo'q; webhook yadrosi hamyon
      to'ldirishga (E5.4) ulanadi
- [ ] ~~Push/SMS ni ulash~~ — Faza E: push abstraksiyasi olib tashlanadi (E4.8); Telegram + in-app qoladi
- [ ] Redis fan-out (ko'p instansiya WS), `X-Forwarded-For` ishonchli proxy ro'yxati
- [ ] ~~Real PSP adapteri~~ — Faza E: to'lov yo'q. Yurist: foydalanuvchi shartlari (E2.14) va hamyon
      provayderi (E5.4)
- [ ] Auksion dvigateli: proxy max rezervni qoplasa, ko'rinadigan narx rezervgacha KO'TARILMAYDI
      (eBay ko'taradi). Natija: yagona bidder max=6000, rezerv=5000 bo'lsa auksion 1100 da
      RESERVE_NOT_MET bilan yopiladi. → Faza E: rezerv olib tashlanadi (E4.2), muammo o'zi yo'qoladi
- [ ] Taklif order'i to'lanmasa avtomatik bekor qilish → Faza E: kelishuv modeli (E2): bog'lanish
      oynasi, bekor qilish sababi, zaxira qaytishi
- [ ] Taklifli e'lonlar uchun kuzatuv ro'yxati va "tugashiga oz qoldi" → Faza E E6.3
- [ ] `message-thread.tsx`: suhbatdagi havola `/lot/{item_id}` — auksion id kutiladi (oldindan bor xato)
- [ ] Moderatsiya: auksioni **allaqachon sotilmay tugagan** e'lonni admin rad etsa, rad
      etish hech qayerda saqlanmaydi (closer item'ni baribir `CANCELLED` qiladi) — sotuvchi
      uni `POST /auctions/{id}/relist` bilan qaytara oladi. Jonli auksion rad etilganda bu
      yopiq (auksion `CANCELLED` -> relist 409). Yechim: `items.rejected_at` (yoki moderatsiya
      holati) ustuni + relist'da tekshiruv. → Faza E E3.8 (`rejected` holati)

## Qat'iy tartib qoidasi

Fazalar **ketma-ket**. Sabab:
- Faza C (atomik bid) Faza A'siz **sinab bo'lmaydi** — SQLite `FOR UPDATE`ni indamay yutadi,
  test yashil bo'ladi, prod'da ma'lumot buziladi.
- Faza D (escrow) Faza B'siz — Numeric/int aralashmasi pul hisobida xatoga olib keladi.
- Real-time Faza C'siz — noto'g'ri narxni tez tarqatishdan boshqa foyda yo'q.

Faza D qamrovdan chiqarildi (Faza E). Endi: **Faza E bosqichlari ketma-ket** —
P → E0 → (E1 + E2, bitta reliz) → E3 → E4 → E5 / E6. Faza E tugamasdan bosqichlarga kirmagan
yangi feature qo'shilmaydi. Har bosqichdan keyin parallel bid, parallel buy-now va parallel taklif
qabuli testlari o'zgarishsiz yashil bo'lishi shart.
