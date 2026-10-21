# Autentifikatsiya va sessiyalar

Maqsad: foydalanuvchi 30 daqiqalik access token eskirgani uchun **chiqib ketmaydi**;
sessiya faqat u tugaganda (14 kun faolsizlik yoki 30 kunlik mutlaq chegara), bekor
qilinganda yoki o'g'irlik belgisi ko'ringanda yopiladi. Email/parol va Google — bitta
sessiya modeli (`AuthService._start_session`).

## Tokenlar

| Token | Umri | Qayerda | Kim o'qiydi |
|---|---|---|---|
| Access (JWT, `type=access`) | 30 daq (`ACCESS_TOKEN_EXPIRE_MINUTES`) | Brauzer **xotirasida** (`lib/api/token.ts`) | `Authorization: Bearer`; WebSocket'da birinchi `AUTH` xabari |
| Refresh (JWT, `type=refresh`, `sid` + `jti`) | 14 kun sirpanuvchi (`REFRESH_TOKEN_EXPIRE_DAYS`), lekin login'dan ko'pi bilan 30 kun (`REFRESH_SESSION_MAX_DAYS`) | **HttpOnly cookie** `bazart_refresh`, `Path=/api/v1/auth` | Faqat backend |

Refresh token JSON javobda **qaytarilmaydi**, `localStorage`'da saqlanmaydi va log'ga
yozilmaydi — XSS uni o'qiy olmaydi. `localStorage`'da faqat maxfiy bo'lmagan
`bazart-session=1` belgisi turadi ("bu brauzerda sessiya bor": anonim mehmon behuda
`/auth/refresh` chaqirmasin; tablar login/logout'ni `storage` hodisasidan biladi).

## Sessiya jadvali (`auth_sessions`)

Bitta kirish = bitta qator: `user_id`, `current_jti`, `previous_jti`, `rotated_at`,
`created_at`, `expires_at`, `revoked_at`, `revoke_reason` (`logout` | `reuse` |
`password_reset`). Token o'zi saqlanmaydi — faqat `jti`. Sessiya holati Postgres'da
(ACID), Redis'ga bog'liq emas.

## Endpointlar

| Endpoint | Nima qiladi |
|---|---|
| `POST /auth/login`, `POST /auth/google` | Yangi sessiya; javob `{access_token, token_type, expires_in}` + `Set-Cookie` |
| `POST /auth/refresh` | Cookie bilan; **rotation** — yangi access + yangi refresh cookie. 401 = sessiya tugagan (cookie ham tozalanadi) |
| `POST /auth/logout` | Access token **shart emas** (eskirgan bo'lsa ham ishlaydi): access -> blacklist, sessiya -> `revoked`, cookie tozalanadi |
| `POST /auth/reset-password` | Foydalanuvchining barcha sessiyalari yopiladi |
| `WS /ws/auctions/{id}` | Ulangach birinchi xabar `{"type":"AUTH","token":"<access>"}` -> `{"type":"AUTH_OK"}`; 10 s ichida kelmasa yoki yaroqsiz — 4401 |

## Rotation va replay detection (`AuthService.refresh_session`)

Sessiya qatori `SELECT ... FOR UPDATE` bilan qulflanadi (`test_concurrent_refresh_with_same_token_keeps_session`
— qulf olib tashlansa yiqiladi).

1. `jti == current_jti` -> yangi `jti`, `previous_jti = eski`,
   `expires_at = min(now + 14 kun, created_at + 30 kun)`.
2. `jti == previous_jti` va `rotated_at` dan `REFRESH_REUSE_GRACE_SECONDS` (10 s) o'tmagan ->
   parallel so'rov: **hozirgi** token qayta beriladi, muddat **uzaymaydi**.
3. Boshqa har qanday holat (eski token oynadan keyin, ikki rotation oldingi token) ->
   o'g'irlangan token belgisi: **butun sessiya bekor**, ikkala tomon ham qayta kiradi.
   Log'ga faqat `auth_session_id` va `user_id` yoziladi.
4. `created_at + REFRESH_SESSION_MAX_DAYS` o'tgan sessiya faol bo'lsa ham 401 — qayta login.

Foydalanuvchi faol emas yoki o'chirilgan bo'lsa refresh 401 qaytaradi.

### Grace oynasi xavfsizligi

Grace oynasi kerak: sahifa refresh paytida yangilangan, javobi yo'qolgan (mobil tarmoq)
yoki Web Locks'siz brauzer — aks holda halol foydalanuvchi "reuse" deb chiqarib yuborilardi.
Bir xil brauzerdagi tablar Web Lock bilan navbatlashadi, shuning uchun oyna qisqa (10 s).

Chegaralar (testlar bilan isbotlangan):
- Grace yo'li muddatni uzaytirmaydi — replay qiluvchi sessiyani sura olmaydi
  (`test_grace_reissue_does_not_extend_session`).
- `previous_jti` faqat bitta qadam: hujumchi doim yangilab tursa ham egasining eski tokeni
  ikki qadam orqada qoladi va keyingi refresh'da sessiya yopiladi
  (`test_stolen_token_used_first_is_detected_when_owner_returns`, `test_token_two_rotations_old_is_replay`).
- Oldindan o'g'irlangan (eski) token grace'dan keyin ishlatilsa — darhol sessiya bekor
  (`test_replay_outside_grace_revokes_whole_session`).
- Qolgan xavf: hujumchi tokenni **real vaqtda** (egasi ishlatgan 10 s ichida) olsa,
  egasi navbatdagi refresh qilguncha sessiyani bo'lishadi. Bunday hujumchi (qurilmadagi
  zararli dastur, TLS'siz tarmoq) yangi cookie'ni ham o'g'irlay oladi — grace xavfni
  oshirmaydi. Egasi uzoq faolsiz bo'lsa ham sessiya 30 kunlik mutlaq chegarada tugaydi.

## CSRF

Cookie'ni brauzer o'zi yuboradi, shuning uchun `/auth/refresh` va `/auth/logout`:
- `SameSite=Lax` (frontend va API bitta saytda: `bazart.uz` + `api.bazart.uz`, local'da `localhost:3000` + `:8000`);
- `Origin` sarlavhasi bo'lsa — `CORS_ORIGINS` ro'yxatida bo'lishi shart, aks holda 403.

## Redis'siz holat

| Nima | Redis bor | Redis yo'q (in-memory zaxira) |
|---|---|---|
| Refresh sessiyalar, rotation, logout'da sessiya bekor qilish | Postgres | Postgres — **o'zgarmaydi** |
| Logout'dagi access token blacklist | Barcha worker'lar | Faqat shu process, restart'da yo'qoladi — access token o'z muddatigacha (≤30 daq) ishlashi mumkin |
| Eski (sid'siz) token ko'chirishdagi blacklist | Umumiy | Process-ichi |

## Frontend (`lib/api/client.ts`, `lib/store/auth.ts`)

- **Proaktiv:** access tokenga 60 s dan kam qolgan bo'lsa so'rovdan oldin yangilanadi.
- **Reaktiv:** so'rov 401 olsa — bitta refresh, so'rov **bir marta** takrorlanadi.
- **Single-flight:** tab ichida bir vaqtda bitta refresh; parallel so'rovlar shu va'dani kutadi.
- **Tablar:** refresh `navigator.locks` (`bazart-auth-refresh`) ostida — navbat bilan,
  har biri oldingisi qo'ygan yangi cookie bilan. Logout/login boshqa tablarga `storage` hodisasi orqali.
- **Faqat refresh 401 chiqaradi.** Tarmoq xatosi, 5xx, 403, timeout — `ApiError`, sessiya tegilmaydi.
- **Tiklash:** `status = "idle"` paytida sarlavha va mobil tab-bar skeleton ko'rsatadi
  ("Kirish" chiqmaydi). `loadMe` -> kerak bo'lsa refresh -> `/auth/me`. Backend yo'q bo'lsa
  `idle` qoladi, backoff (1 s ... 30 s) va `online` hodisasi bilan qayta urinadi.
- **WebSocket:** token URL'da emas — har (qayta) ulanishda `getFreshAccessToken()` va birinchi
  `AUTH` xabari; `status = "open"` faqat `AUTH_OK` dan keyin.
- **Eski klientlar:** `localStorage["bazart-auth"]`dagi refresh token bir marta body orqali
  `/auth/refresh`ga yuboriladi (eski `jti` blacklist, yangi sessiya + cookie), kalit o'chiriladi.

## Prod sozlamalari (deploy oldidan tekshiruv)

| Sozlama | Talab | Kod himoyasi |
|---|---|---|
| `ENVIRONMENT=production` | Secure cookie avtomatik | `REFRESH_COOKIE_SECURE=false` bilan ilova ko'tarilmaydi |
| HTTPS | API va frontend faqat HTTPS (reverse proxy'da TLS + HSTS) | Secure cookie HTTP'da yuborilmaydi |
| `CORS_ORIGINS` | Aniq frontend origin'lari (`https://bazart.uz`, kerak bo'lsa `https://www.bazart.uz`) | Shu ro'yxat Origin tekshiruvida ham ishlatiladi |
| `REFRESH_COOKIE_SAMESITE` | `lax` — frontend va API bitta registrlanuvchi domen ostida | `none` faqat Secure bilan |
| `REFRESH_COOKIE_DOMAIN` | Berilmaydi (cookie faqat API hostiga) | Bo'sh qiymat `None` deb olinadi |
| `NEXT_PUBLIC_API_URL` | `https://api...` (WS `wss://`) | — |
| Redis | Ulangan (access blacklist barcha worker'larda) | Yo'q bo'lsa — yuqoridagi jadval |
| `SMS_PROVIDER` | `eskiz` + `ESKIZ_EMAIL/PASSWORD/SENDER` (secret'da) | log/null/noma'lum bilan ilova ko'tarilmaydi |
| Eskiz shabloni | OTP matni Eskiz kabinetida tasdiqlangan | — |

### Prod RELEASE BLOCKER'lari (telefon OTP) — hal qilinmaguncha prod'ga chiqarilmaydi

1. **Eskiz integratsiyasi haqiqiy hisobda tekshirilmagan.** `EskizSmsProvider` faqat soxta HTTP
   javoblar bilan sinalgan (`httpx.MockTransport`). Chiqarishdan oldin: Eskiz hisobida OTP
   shabloni tasdiqlanadi, staging'da real raqamga SMS yuborilib, kod kelishi, 401 da qayta login
   va xato holatlari qo'lda tekshiriladi.
2. **`X-Forwarded-For` ishonchli proxy bilan cheklanmagan.** OTP va umumiy rate limiter mijoz IP'sini
   XFF ning birinchi qiymatidan oladi — mijoz uni soxtalashtirib IP limitlarini chetlab o'ta oladi.
   Chiqarishdan oldin: `TRUSTED_PROXIES` (yoki uvicorn `--forwarded-allow-ips`) bilan faqat o'z
   reverse proxy'imizdan kelgan XFF qabul qilinadi (ROADMAP "Xavfsizlik backlog").

Frontend boshqa saytda bo'lsa (`SameSite=None` kerak) — Origin tekshiruvi yetarli emas,
CSRF token qo'shilishi kerak (hozir qamrovda emas).

## Telefon tasdig'i (OTP)

**Progressiv tasdiq:** ro'yxatdan o'tish (email/parol yoki Google), ko'rish, qidiruv, kuzatuv
va e'lon **qoralamasi** — tasdiqsiz. Telefon faqat kelishuvga olib boradigan amallarda talab
qilinadi (`CurrentVerifiedUser`, 403 `phone_verification_required`):

| Amal | Tasdiq |
|---|---|
| Ko'rish, qidiruv, kuzatuv, qoralama yaratish | Yo'q |
| E'lonni chiqarish (`publish`), auksion yaratish, qayta joylash | Kerak |
| Taklif berish / qabul qilish / qarshi taklif | Kerak |
| Bid, buy-now, pasayuvchi auksionda xarid, keyingi bidder taklifini qabul qilish | Kerak |
| Kelishuvda kontakt | Faqat tasdiqlangan raqam ochiladi |

Frontend 403 ni ushlaydi (`apiFetch` + `PhoneGateProvider`): tasdiqlash oynasi ochiladi,
tasdiqlangach **asl so'rov bir marta takrorlanadi** — foydalanuvchi amalini qaytadan
boshlamaydi. Sessiya, refresh cookie va boshqa tablar ta'sirlanmaydi (tasdiq — `users`
qatoridagi maydon).

**Raqam:** `+998XXXXXXXXX` (E.164). `normalize_phone` erkin kiritishni (`90 123 45 67`,
`998…`, `+998 90 123-45-67`, `00998…`) bitta ko'rinishga keltiradi; faqat tuzilma
tekshiriladi — raqam faol va egasiniki ekanini SMS kodi isbotlaydi.
**Bitta tasdiqlangan raqam = bitta faol akkaunt:** `uq_users_verified_phone` (qisman UNIQUE,
`phone_verified_at IS NOT NULL AND deleted_at IS NULL`); to'qnashuv — 409 `phone_taken`.
O'chirilgan akkaunt raqamni bo'shatadi, bloklangani — yo'q.

**Hayot sikli** (`OtpService`, endpointlar `/auth/otp/request`, `/auth/otp/verify` — login majburiy):

1. `request` — kod `secrets` bilan (6 raqam), DBda faqat HMAC-SHA256 (`SECRET_KEY`);
   `otp_codes.user_id` — kodni faqat shu akkaunt ishlatadi. Yangi kod eskilarini bekor qiladi.
   SMS provayder xatosi — kod o'chiriladi, 503 `sms_send_failed`, cooldown sarflanmaydi.
2. `verify` — kod qatori `FOR UPDATE`: bir kod bir marta, urinishlar hisobi yo'qolmaydi.
   To'g'ri kod raqamni akkauntga yozadi va tasdiqlaydi (bitta tranzaksiya).
3. Muddat 5 daqiqa, 5 noto'g'ri urinishdan keyin kod bloklanadi (yangisini so'rash kerak).

**Suiiste'mol cheklovlari** (sozlanadi, SMS narxiga qarab):

| Cheklov | Default | Sozlama |
|---|---|---|
| Kod muddati | 300 s | `OTP_TTL_SECONDS` |
| Urinishlar | 5 | `OTP_MAX_ATTEMPTS` |
| Qayta yuborish (raqam va akkaunt bo'yicha) | 60 s | `OTP_RESEND_COOLDOWN_SECONDS` |
| Kunlik: raqamga / akkauntga / IP'ga | 5 / 10 / 20 | `OTP_DAILY_LIMIT_PER_PHONE/USER/IP` |
| Endpoint (IP, daqiqasiga; CGNAT uchun kengroq, alohida bucket) | 20 | `RATE_LIMIT_OTP_PER_MINUTE` |

`request` raqam boshqa akkauntda tasdiqlanganini aytmaydi (raqamlarni sinab kimniki ekanini
bilib bo'lmasin) — bu faqat kod to'g'ri kiritilgach (egalik isbotlangach) 409 bilan aytiladi.
Log'larda kod hech qachon, raqam esa niqoblangan (`+99890*****67`) holda.

**Raqamni almashtirish:** tasdiqlangan raqam `PATCH /users/me` bilan almashtirilmaydi
(409 `phone_change_requires_verification`). Yangi raqamga kod so'raladi — **qayta
autentifikatsiya**: joriy parol YOKI so'nggi `PHONE_CHANGE_REAUTH_MINUTES` (15) ichida login
(access token'dagi `auth_time` — sessiya boshi, jim refresh'da o'zgarmaydi; Google
foydalanuvchisi parolni bilmaydi). Aks holda 403 `reauth_required`. Eski raqam yangisi
tasdiqlanmaguncha joyida qoladi; almashtirilgach `PHONE_CHANGED` bildirishnomasi (in-app +
Telegram). Eski raqam talab qilinmaydi — uni yo'qotgan foydalanuvchi qamalib qolmaydi;
akkauntni tiklash — parolni tiklash (email) orqali, keyin yangi raqam tasdiqlanadi.
Kelishuvlar, e'lonlar va bidlar o'zgarmaydi.

**SMS provayderlari** (`app/services/sms_provider.py`, `SMS_PROVIDER`):

| Provayder | Qachon | Izoh |
|---|---|---|
| `log` | local/test | SMS yubormaydi; log'da kod niqoblangan; kod faqat non-prod javobidagi `debug_code` da |
| `null` | — | kanal o'chiq (yuborish xato hisoblanadi) |
| `eskiz` | prod | `ESKIZ_EMAIL`, `ESKIZ_PASSWORD`, `ESKIZ_SENDER`; token keshlanadi, 401 da qayta login; tarmoq/5xx — bitta qayta urinish |

Prod/staging'da `log`, `null` yoki noma'lum provayder bilan ilova **ko'tarilmaydi**
(`OTP_ENABLED=false` bundan mustasno). `debug_code` faqat non-prod VA `log` provayderida.
Eskiz OTP matn shablonini oldindan tasdiqlaydi — matn `OtpService` dagi bilan aynan bir xil
bo'lishi kerak: `Bazart tasdiqlash kodi: {kod}. Amal qilish muddati: 5 daqiqa.`

**Mavjud foydalanuvchilar** (migratsiya `0038`): raqamlar E.164 ga keltiriladi;
keltirib bo'lmaydigan raqam saqlanadi, tasdig'i olinadi; bir raqam bir nechta akkauntda
tasdiqlangan bo'lsa — eng birinchisi qoladi, qolganlari qayta tasdiqlaydi. Hech kim tizimdan
chiqarilmaydi. Endi qoralama tasdiqsiz yaratiladi.

## Testlar

- Backend: `tests/test_auth_sessions.py` (rotation, grace, replay, poyga + mutatsiya, mutlaq
  muddat, logout, Origin, eski token, parol tiklash, prod cookie bayroqlari, yangilangan token
  bilan bid/taklif, log'da token yo'q), `tests/test_google_auth.py::test_google_login_gets_same_refresh_session`,
  `tests/test_ws_auth.py` (AUTH xabari, timeout, eski `?token=`).
- Telefon OTP: `tests/test_otp.py` (format, tasdiq, eskirish, urinishlar, cooldown, kunlik
  limitlar, qayta ishlatish, parallel tekshiruv + mutatsiya, akkauntga bog'liqlik, bitta raqam =
  bitta akkaunt, almashtirish va qayta autentifikatsiya, Google, sessiya, marketplace gate,
  log/javobda sir yo'q, SMS xatosi, Eskiz adapteri, prod cheklovlari), `tests/test_phone_gate.py`.
- Frontend: `frontend/lib/phone.test.ts`, `frontend/lib/api/phone-gate.test.ts`,
  `frontend/lib/api/session.test.ts` (`npm test`, Vitest) — single-flight, retry-once,
  401/403/500/tarmoq, tablar (Web Lock), tiklash, logout, eski token ko'chirish.
- Haqiqiy brauzer (Microsoft Edge, 2026-10-20, 27/27): email login, cookie bayroqlari, reload
  (skeleton, "Kirish" miltillamaydi), WS `AUTH`/`AUTH_OK`, 2 daqiqalik access TTL bilan jim
  yangilash, 3 tab bir vaqtda, backend o'chiq/503/tarmoq xatosi, logout sinxroni, brauzer
  restart, eskirgan sessiya, Google tugmasi render. **Google bilan haqiqiy kirish** real Google
  akkaunt talab qiladi — qo'lda tekshiriladi (backend yo'li testlarda qoplangan).

## Cheklovlar / TODO

- `LEGACY_REFRESH_BODY_ENABLED` va WS `?token=` — bir reliz/14 kundan keyin o'chirish.
- Eskirgan/bekor qilingan `auth_sessions` qatorlarini tozalovchi beat vazifasi yo'q.
- Access token sessiya bekor bo'lgach ham o'z muddatigacha (≤30 daq) ishlaydi
  (logout'da esa darhol blacklist'ga tushadi, Redis bo'lsa).
- WS ulanish faqat ulanish paytida tekshiriladi; ochiq socket token eskirgach ham ishlaydi.
- OTP IP limiti `X-Forwarded-For` ning birinchi IP'siga ishonadi (umumiy rate limiter kabi) —
  ishonchli proxy ro'yxati sozlanmaguncha soxtalashtirish mumkin (ROADMAP).
- Eski (`auth_time`siz) access token'li sessiyalar raqamni almashtirishda parol so'raydi.
