from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Kod ichida yozilgan zaif defaultlar. Prod/staging'da bu qiymatlar bilan
# ishga tushish TAQIQ (JWT qalbakilashtirish / soxta webhook imzo xatari).
INSECURE_DEFAULT_SECRET_KEY = "change-me-in-production-secret-key"
INSECURE_DEFAULT_WEBHOOK_SECRET = "change-me-webhook-secret"

Environment = Literal["local", "test", "staging", "production"]
# OTP kodini haqiqatan yetkazadigan provayderlar (app/services/sms_provider.py).
REAL_SMS_PROVIDERS = frozenset({"eskiz"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Bazart API"
    environment: Environment = "local"
    # 5433 — docker compose'dagi Postgres host porti (5432 mahalliy
    # o'rnatilgan Postgres tomonidan band bo'lishi mumkin).
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/bazart"
    secret_key: str = Field(default=INSECURE_DEFAULT_SECRET_KEY, min_length=32)
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    # Refresh token HttpOnly cookie'da (JS o'qiy olmaydi). Path faqat /auth — boshqa
    # so'rovlarga yuborilmaydi. Secure: None bo'lsa prod/staging'da yoqiladi (localhost http).
    refresh_cookie_name: str = "bazart_refresh"
    refresh_cookie_path: str = "/api/v1/auth"
    refresh_cookie_domain: str | None = None
    refresh_cookie_secure: bool | None = None
    # Lax: frontend va API bitta saytda (bazart.uz + api.bazart.uz, localhost:3000 + :8000).
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    # Sirpanuvchi muddat (refresh_token_expire_days) bilan ham sessiya login'dan shuncha kun
    # o'tgach albatta tugaydi: o'g'irlangan va doim yangilanib turgan sessiya abadiy yashamasin.
    refresh_session_max_days: int = 30
    # Oldingi refresh token shu oynada kelsa replay emas (sahifa refresh paytida yangilandi,
    # javob yo'qoldi, Web Locks'siz brauzer). Tablar Web Lock bilan navbatlashgani uchun qisqa.
    refresh_reuse_grace_seconds: int = 10
    # Eski klientlar (refresh token localStorage'da) bir marta body orqali o'tkaziladi.
    # TODO(ROADMAP): 14 kundan keyin (eski tokenlar eskirgach) o'chirish.
    legacy_refresh_body_enabled: bool = True
    password_reset_token_expire_minutes: int = 30
    email_verification_token_expire_minutes: int = 60
    soft_close_window_seconds: int = 120
    soft_close_extension_seconds: int = 120
    # Anti-sniping cheksiz cho'zilmasin: bir auksion ko'pi bilan shuncha marta
    # uzaytiriladi. Undan keyin oxirgi soniyadagi bid muddatni surmaydi.
    max_soft_close_extensions: int = 10
    local_upload_dir: str = "uploads"
    public_upload_url_prefix: str = "/uploads"
    algorithm: str = "HS256"

    # Auksionni avtomatik yopuvchi fon vazifasi.
    # Default False: testlarda fon vazifasi ishga tushib test bazasini
    # o'zgartirmasligi kerak. Local/prod'da .env orqali yoqiladi.
    auction_closer_enabled: bool = False
    auction_closer_interval_seconds: int = 5
    # "Tugashiga oz qoldi" eslatmasi: auksion tugashidan shuncha daqiqa oldin
    # kuzatuvchi va bidderlarga bir marta yuboriladi (closer bilan bir tik'da).
    # 2 soat: oxirgi raqobatga qaytish uchun yetarli vaqt (mahsulot talabi).
    ending_soon_lead_minutes: int = 120
    ending_soon_interval_seconds: int = 60
    # Taklifli savdo: muddati o'tgan takliflar va e'lonlarni yopish oralig'i.
    offer_expiry_interval_seconds: int = 60
    # "Narx tushdi" (pasayuvchi auksion): kuzatuvchilarga oxirgi xabardagi narxdan kamida
    # shuncha bps (1000 = 10%) pasaygach yoki chegaraga yetganda bir marta xabar — har
    # soatlik pasayishda emas (spam bo'lmasin).
    price_drop_notify_min_bps: int = 1000
    price_drop_interval_seconds: int = 300
    # Telegram/push xabarlarida lot/buyurtma havolasi uchun sayt manzili (bo'sh — havolasiz).
    public_site_url: str = ""

    # Dinamik (darajali) minimal stavka qadami poli. Prod'da yoqiq: narxga
    # qarab qadam avtomatik oshadi (5 000 so'mdan boshlab). Test muhitida
    # conftest uni o'chiradi — kichik-summali mavjud test korpusi buzilmasin;
    # jadval mantig'i pure-function + bitta integratsiya testida tekshiriladi.
    tiered_bid_increment_enabled: bool = True
    # O'suvchi (ingliz) auksion: False — YANGI o'suvchi auksion yaratilmaydi va UI'da
    # yashiriladi. Mavjudlari (bid, yopish, second chance, fallback) o'z qoidasida
    # tugaydi. Qayta yoqish — faqat shu bayroq (migratsiyasiz). docs/AUCTION_ENGINE.md §14.
    feature_ascending_auction: bool = False

    # Rate limiting (bid/login brute-force himoyasi).
    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = 5
    rate_limit_bid_per_minute: int = 10
    rate_limit_otp_per_minute: int = 20

    # To'lov provayderi webhook imzo kaliti. Bazart savdo to'lovida ishtirok etmaydi
    # (Faza E); kalit hamyon to'ldirish webhook'i uchun saqlanadi (E5).
    psp_webhook_secret: str = INSECURE_DEFAULT_WEBHOOK_SECRET

    # Kelishuv (Faza E2, docs/DEALS.md).
    # Kelishuvdan keyin bog'lanish oynasi: shundan keyingina "javob bermadi" bilan bekor qilinadi.
    deal_contact_window_hours: int = 48
    # "Sotildi" dan keyin xaridor jim tursa (va ochiq shikoyat bo'lmasa) avto-tasdiq.
    deal_auto_confirm_hours: int = 72
    deal_auto_confirm_interval_seconds: int = 300
    # Keyingi bidderga taklif (E2.10) muddati o'tganini qayd etish va sotuvchiga xabar.
    next_offer_expiry_interval_seconds: int = 300
    # Bekor qilish cheklovi: oynada shuncha aybli bekor qilish -> shuncha kun bid/taklif taqiqi.
    deal_cancel_limit: int = 3
    deal_cancel_window_days: int = 30
    deal_cancel_ban_days: int = 14

    # Redis (token blacklist, keyin kesh/pub-sub). Bo'sh bo'lsa in-memory fallback.
    redis_url: str = "redis://localhost:6379/0"
    # Frontend (Next.js) origin'lari — brauzerdan API'ga so'rov yuborishi uchun CORS.
    # .env orqali JSON ro'yxat sifatida beriladi: CORS_ORIGINS='["https://bazart.uz"]'
    cors_origins: list[str] = ["http://localhost:3000"]

    # Celery (fon vazifalari: auksion yopish, takliflar muddati, push, email).
    # Broker/backend berilmasa — redis_url ishlatiladi.
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    # True bo'lsa vazifa worker'siz, chaqiruv joyida (inline) bajariladi.
    # Test/worker yo'q local uchun qulay; prod'da False (worker bajaradi).
    celery_task_always_eager: bool = False
    # Celery beat davriy vazifalarini yoqish (prod'da True). Yoqilganda
    # in-process pollerlar (main.py lifespan) o'rniga Celery beat ishlaydi.
    celery_beat_enabled: bool = False

    @property
    def effective_celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def effective_celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def celery_eager(self) -> bool:
        """Test muhitida doim inline — worker/broker talab qilinmaydi."""
        return self.celery_task_always_eager or self.environment == "test"

    # Fayl yuklash cheklovlari (stored XSS / DoS himoyasi).
    upload_max_bytes: int = 5_000_000  # 5 MB
    # Bir e'longa maksimal rasm soni.
    max_images_per_item: int = 10

    # Telegram bildirishnoma (O'zbekiston uchun asosiy kanal — "stavkangiz
    # oshib ketdi" xabari push o'rnida). Token bo'sh / enabled False bo'lsa
    # yetkazib berish log provayderga tushadi (graceful, ilova yiqilmaydi).
    telegram_enabled: bool = False
    telegram_bot_token: str = ""
    telegram_api_timeout_seconds: float = 10.0

    # OTP / telefon tasdiqlash (SMS). sms_provider="log" — kod log'ga yoziladi
    # (local/test); real provayder keyin ulanadi. Kodlar HASH bilan saqlanadi.
    otp_enabled: bool = True
    sms_provider: str = "log"  # "log" | "eskiz" | ... (real provayder keyin)
    otp_ttl_seconds: int = 300  # kod amal qilish muddati (5 daqiqa)
    otp_code_length: int = 6
    otp_max_attempts: int = 5  # noto'g'ri urinishdan keyin kod bloklanadi
    otp_resend_cooldown_seconds: int = 60  # 1 SMS / 60 soniya
    otp_daily_limit_per_phone: int = 5  # kuniga bir raqamga
    otp_daily_limit_per_ip: int = 20  # kuniga bir IP'ga
    otp_daily_limit_per_user: int = 10  # kuniga bir akkauntga (bir necha raqam sinab ko'rish)
    # Tasdiqlangan raqamni almashtirish: joriy parol YOKI shuncha daqiqa ichida login talab
    # qilinadi (o'g'irlangan sessiya bilan raqamni hujumchinikiga almashtirib bo'lmasin).
    phone_change_reauth_minutes: int = 15
    # Eskiz.uz (sms_provider="eskiz"). Hisob ma'lumotlari faqat .env/secret'da.
    eskiz_base_url: str = "https://notify.eskiz.uz/api"
    eskiz_email: str = ""
    eskiz_password: str = ""
    # Eskiz'da tasdiqlangan jo'natuvchi nomi (alpha-name) yoki qisqa raqam.
    eskiz_sender: str = "4546"
    sms_timeout_seconds: float = 10.0

    # Google orqali kirish (Google Identity Services ID token). Bo'sh bo'lsa
    # /auth/google o'chiq (503). Qiymat — Google Cloud'dagi OAuth Web Client ID;
    # ID token `aud` maydoni aynan shu bilan solishtiriladi: boshqa ilova uchun
    # chiqarilgan token bizda kirish uchun ishlatilmasin.
    google_client_id: str = ""

    @property
    def is_production(self) -> bool:
        """Prod yoki staging — ya'ni real pul va real foydalanuvchilar muhiti."""
        return self.environment in {"staging", "production"}

    @property
    def refresh_cookie_secure_effective(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.is_production

    @model_validator(mode="after")
    def _forbid_insecure_secret_in_production(self) -> "Settings":
        """Prod/staging'da default SECRET_KEY bilan ishga tushishni bloklaydi.

        Default secret bilan ishlasa istalgan odam istalgan foydalanuvchi
        nomidan JWT qalbakilashtira oladi. Shuning uchun bu xato ogohlantirish
        emas — ilova umuman ko'tarilmaydi.
        """
        if self.is_production and self.secret_key == INSECURE_DEFAULT_SECRET_KEY:
            raise ValueError(
                f"SECRET_KEY '{self.environment}' muhitida default qiymatda qolgan. "
                'Kuchli tasodifiy qiymat bering: python -c "import secrets; '
                'print(secrets.token_urlsafe(48))"'
            )
        if self.is_production and self.psp_webhook_secret == INSECURE_DEFAULT_WEBHOOK_SECRET:
            raise ValueError(
                f"PSP_WEBHOOK_SECRET '{self.environment}' muhitida default qiymatda qolgan. "
                "Soxta webhook imzosi bilan tovar bepul ketishi mumkin — kuchli kalit bering."
            )
        if self.is_production and not self.refresh_cookie_secure_effective:
            raise ValueError("REFRESH_COOKIE_SECURE prod/staging'da o'chirilmaydi (faqat HTTPS).")
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_secure_effective:
            raise ValueError("SameSite=None faqat Secure cookie bilan ishlaydi.")
        if self.refresh_session_max_days < self.refresh_token_expire_days:
            raise ValueError("REFRESH_SESSION_MAX_DAYS < REFRESH_TOKEN_EXPIRE_DAYS bo'lmaydi.")
        if self.is_production and self.otp_enabled:
            # log/null provayderda kod foydalanuvchiga yetmaydi (yoki log'ga tushadi).
            if self.sms_provider not in REAL_SMS_PROVIDERS:
                raise ValueError(
                    f"SMS_PROVIDER={self.sms_provider!r} prod/staging'da ruxsat etilmaydi. "
                    f"Haqiqiy provayder kerak: {sorted(REAL_SMS_PROVIDERS)}"
                )
            if self.sms_provider == "eskiz" and not (self.eskiz_email and self.eskiz_password):
                raise ValueError("SMS_PROVIDER=eskiz uchun ESKIZ_EMAIL va ESKIZ_PASSWORD kerak.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
