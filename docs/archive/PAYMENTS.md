# To'lovlar va escrow

> **ARXIV (2026-10).** Faza E qarori: Bazart to'lovda ishtirok etmaydi. Bu hujjat escrow/PSP dizaynini
> tarix sifatida saqlaydi; kod E1 da olib tashlanadi. Saqlanadiganlar: `core/webhook.py` va
> `webhook_events` (hamyon to'ldirish, E5.4). Joriy model: `docs/DEALS.md`.

Kod: `app/services/payment_service.py`, `app/services/payment_providers.py`,
`app/models/payment.py`, `app/api/v1/endpoints/payments.py`.

## 1. Huquqiy asos — birinchi navbatda

**Biz pulni O'ZIMIZ ushlamaymiz.** Mijoz mablag'ini hisobimizda saqlash O'zbekistonda
litsenziyalangan faoliyat. Litsenziyasiz escrow = jinoiy xatar, hisoblar bloklanishi.

**Model:** litsenziyalangan **PSP** (Payme / Click / Uzum yoki bank) kartada **hold**
(bloklash) qiladi, keyin **capture** yoki **release** qiladi. Biz faqat **orkestratsiya**
qilamiz: qachon hold, qachon capture, qachon bekor — biznes qoidalarini biz yuritamiz,
pul harakati PSP tomonda.

| TODO | Holat |
|---|---|
| Yurist bilan tekshirish: "marketplace hold/capture" modeli litsenziya talab qiladimi | **OCHIQ** |
| PSP shartnomasida hold muddati (necha kun?) va capture API'si bor-yo'qligi | **OCHIQ** |
| Buyer premium (8%) soliqqa qanday rasmiylashadi | **OCHIQ** |

Bu savollar hal bo'lmaguncha real PSP integratsiyasi boshlanmaydi.

## 2. Hozirgi holat

| Element | Holat |
|---|---|
| PSP abstraksiyasi (`BasePaymentProvider` ABC) | **BOR** — `payment_providers.py:19-28` |
| `MockPaymentProvider` | **BOR** — faqat local/test, prod'da bloklangan |
| Provayder registri + noma'lum nom → xato | **BOR** — `get_payment_provider()` |
| Mock guard (`settings.allow_mock_payments`) | **BOR** — `config.py:39-46`, prod/staging'da o'chiq |
| Karta tokenizatsiya (PAN saqlanmaydi) | **BOR** — `models/payment.py:12-23`, faqat `token_reference` |
| IDOR himoyasi (o'z order/payment'ing) | **BOR**, toza |
| **Escrow holatlari (HELD / RELEASED / CANCELLED_HOLD)** | **BOR** — `payment_state.py`, migratsiya 202607170012 |
| **`idempotency_key`** | **BOR** — partial unique, `create_hold` idempotent |
| **Webhook imzo tekshiruvi** | **BOR** — `core/webhook.py` (HMAC, xom bayt), `POST /payments/webhooks/psp` 401 |
| **`audit_log`** | **BOR** — `audit_service.py`, INSERT only, pul operatsiyalariga ulangan |
| **Buyer premium (8%) hisobi** | **BOR** — `money.calc_buyer_premium`, hold summasida |
| **Auto-complete 72 soat** | **BOR** — `auto_complete.py` worker |
| PSP escrow interfeysi (hold/capture/release) | **BOR** — `BasePaymentProvider`, Mock |
| Real PSP adapteri (Payme/Click) | **YO'Q** — huquqiy tekshiruvdan keyin |
| Webhook hodisasini payment'ga ulash (event->status) | **YO'Q** — imzo bor, ishlov qism TODO |

## 3. PSP adapter shartnomasi

Hozirgi ABC (`payment_providers.py`):

```python
class BasePaymentProvider(ABC):
    provider_name: str

    @abstractmethod
    def create_payment(self, *, amount: Decimal, currency: str) -> PaymentProviderResult: ...

    @abstractmethod
    def confirm_payment(self, *, provider_payment_id: str) -> PaymentProviderResult: ...
```

**Maqsadli shartnoma (Faza D):**

```python
class BasePaymentProvider(ABC):
    provider_name: str

    @abstractmethod
    def create_hold(
        self, *, amount_tiyin: int, currency: str, token_reference: str, idempotency_key: str
    ) -> ProviderResult:
        """Kartada mablag'ni bloklaydi (escrow o'rnini bosadi). Pul hali ko'chmaydi."""

    @abstractmethod
    def capture(self, *, provider_payment_id: str, idempotency_key: str) -> ProviderResult:
        """Bloklangan mablag'ni yechadi — tovar topshirilgandan keyin."""

    @abstractmethod
    def release(self, *, provider_payment_id: str, idempotency_key: str) -> ProviderResult:
        """Blokni bekor qiladi — kelishuv buzilganda, pul xaridorda qoladi."""

    @abstractmethod
    def verify_webhook(self, *, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
        """Imzoni tekshiradi. Imzo noto'g'ri bo'lsa ISTISNO — hodisa qabul qilinmaydi."""
```

Har PSP shu interfeysni implement qiladi va `_PROVIDERS` registriga qo'shiladi.
Biznes kod PSP nomini bilmaydi — faqat interfeysni.

## 4. Escrow oqimi (maqsad)

```
Auksion yopildi → Order(pending_payment)
        │
        ▼
  create_hold(total_amount)      ──► PSP kartada bloklaydi
        │                             Payment.status = HOLD
        ▼
  Sotuvchi tovarni topshiradi
  Xaridor tasdiqlaydi  ──yoki── 72 soat sukut → auto-complete
        │
        ▼
  capture()  ──► pul sotuvchiga (minus komissiya)
                 Payment.status = RELEASED
                 Order.status = completed

  Nizo / topshirilmadi:
  release()  ──► blok bekor, pul xaridorda
                 Payment.status = CANCELLED_HOLD
                 Order.status = cancelled
```

**Kerakli yangi `PaymentStatus` qiymatlari:** `HOLD`, `RELEASED`, `CANCELLED_HOLD`.
Hozirgi enum: `pending`, `processing`, `paid`, `failed`, `refunded` — escrow'ni ifodalay olmaydi.

**Buyer premium:** 8% (BPS = 800).
```python
BUYER_PREMIUM_BPS = 800
premium = final_price_tiyin * BUYER_PREMIUM_BPS // 10_000  # butun bo'linma, float TAQIQ
total = final_price_tiyin + premium
```
Yaxlitlash doim tiyingacha, `//` orqali. `float` ishlatish **TAQIQ**.

## 5. Idempotentlik — MAJBURIY

**Muammo:** tarmoq uzildi, mobil ilova retry qildi → ikki marta hold. Yoki PSP webhook'ni
uch marta yubordi → order uch marta `paid`.

**Qoida:** har pul operatsiyasi `idempotency_key` bilan keladi. Kalit `payments` jadvalida
**unique** — ikkinchi urinish yangi operatsiya yaratmaydi, birinchisining natijasini qaytaradi.

```python
def create_hold(self, payload: HoldCreate, buyer: User) -> Payment:
    """Escrow hold yaratadi. idempotency_key bo'yicha takrorlanmaydi.

    Kalit unique index bilan himoyalangan: parallel ikki so'rov kelsa,
    ikkinchisi IntegrityError oladi va mavjud natijani qaytaradi.
    """
    existing = self.payments.get_by_idempotency_key(payload.idempotency_key)
    if existing is not None:
        return existing  # tekshirmasdan qayta yaratish TAQIQ

    try:
        payment = self.payments.create(..., idempotency_key=payload.idempotency_key)
        self.db.flush()
    except IntegrityError:
        self.db.rollback()
        return self.payments.get_by_idempotency_key(payload.idempotency_key)
    ...
```

Kalit klientdan keladi (UUID). PSP chaqiruviga ham **o'sha** kalit uzatiladi.

## 6. Webhook — imzo majburiy

**KRITIK:** imzosiz webhook = istalgan odam `{"status": "paid"}` yuborib tovarni bepul oladi.

Qoidalar:
1. **Imzo tekshiriladi** (HMAC yoki PSP sxemasi) — **xom bayt** (`await request.body()`) ustida,
   parse qilingan JSON ustida emas.
2. Taqqoslash `hmac.compare_digest` bilan — `==` **TAQIQ** (timing attack).
3. Imzo noto'g'ri → **401**, hech qanday yon effektsiz, hech narsa yozilmaydi.
4. Hodisa **idempotent** qayta ishlanadi: `provider_event_id` unique, takrori e'tiborsiz.
5. Timestamp tekshiriladi (eski hodisa → replay attack).
6. Haqiqat manbai — **PSP holati**, bizning kutganimiz emas. Har webhook'dan keyin holat
   PSP'dan tasdiqlanadi.
7. Webhook endpoint autentifikatsiyadan **ozod**, lekin imzodan **ozod emas**.

## 7. Audit log — YO'Q, qilinadi

Har pul harakati o'zgarmas jurnalga yoziladi: kim, qachon, nima, qaysi qiymatdan qaysiga,
qaysi `idempotency_key`, PSP javobi. Yozuv `INSERT` only — `UPDATE`/`DELETE` **TAQIQ**.

Kerakli maydonlar: `id`, `actor_id` (nullable — worker/webhook uchun), `action`,
`entity_type`, `entity_id`, `old_value` JSONB, `new_value` JSONB, `idempotency_key`,
`ip`, `created_at`.

Nega: nizo chiqqanda ("men to'lamadim" / "men jo'natdim") yagona dalil shu. Loglar yetarli emas —
ular aylanadi va o'chadi.

## 8. Mock provayder — prod'dagi eng katta xatar

`MockPaymentProvider.confirm_payment()` **doim** `PAID` qaytaradi. Prod'da ochiq qolsa —
istalgan xaridor bitta so'rov bilan tovarni bepul oladi.

Hozirgi himoya (**BOR**, `config.py` + `payment_service.py:66-67`):
- `settings.allow_mock_payments` faqat `local` / `test` muhitida `True`.
- `get_payment_provider("mock")` prod'da `PaymentProviderError` beradi.
- `POST /payments/{id}/confirm-mock` prod'da **404** qaytaradi (mavjudligini ham oshkor qilmaydi).
- `tests/test_payment_security.py` — 8 test shu himoyani qo'riqlaydi.

**Bu himoyani zaiflashtirish TAQIQ.** Real PSP kelganda mock butunlay olib tashlanadi.

## 9. Xavfsizlik qoidalari (qisqacha)

| Qoida | Holat |
|---|---|
| PAN / CVV / amal muddati saqlash | **TAQIQ** — hozir toza |
| Karta faqat PSP tokeni orqali (`token_reference`) | BOR |
| Webhook imzosiz qabul | **TAQIQ** — webhook hali yo'q |
| Pul summasi float'da | **TAQIQ** — hozir Decimal, maqsad BIGINT tiyin |
| Order summasi klientdan ishonchli olinadi | **TAQIQ** — server `orders.final_price` bilan solishtiradi (BOR, `payment_service.py:26-30`) |
| Prod'da mock provayder | **TAQIQ** — guard BOR |
| To'lov statusini qo'lda o'zgartirish endpoint'i | **TAQIQ** |
