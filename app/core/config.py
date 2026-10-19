from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Kod ichida yozilgan zaif defaultlar. Prod/staging'da bu qiymatlar bilan
# ishga tushish TAQIQ (JWT qalbakilashtirish / soxta webhook imzo xatari).
INSECURE_DEFAULT_SECRET_KEY = "change-me-in-production-secret-key"
INSECURE_DEFAULT_WEBHOOK_SECRET = "change-me-webhook-secret"

Environment = Literal["local", "test", "staging", "production"]

# Mock to'lov provayderi va mock tasdiqlash faqat shu muhitlarda ruxsat etiladi.
# Prod'da mock = tovarni bepul olish imkoni.
_MOCK_SAFE_ENVIRONMENTS: frozenset[str] = frozenset({"local", "test"})


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

    # Rate limiting (bid/login brute-force himoyasi).
    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = 5
    rate_limit_bid_per_minute: int = 10

    # Escrow / to'lov (Faza D).
    buyer_premium_bps: int = 800  # 8% (basis points)
    auto_complete_hours: int = 72  # xaridor sukut saqlasa order shu vaqtda yakunlanadi
    # PSP webhook imzo maxfiy kaliti. Prod'da .env orqali beriladi.
    psp_webhook_secret: str = INSECURE_DEFAULT_WEBHOOK_SECRET
    # Real PSP (escrow hold/capture/release) HTTP adapteri sozlamalari.
    # Bo'sh psp_base_url = adapter o'chiq (prod'da .env orqali beriladi).
    # "psp" provayderi so'ralsa-yu base_url bo'sh bo'lsa — aniq config xatosi.
    psp_base_url: str = ""
    psp_api_key: str = ""  # so'rov imzosi (HMAC) va Authorization uchun
    psp_timeout_seconds: float = 15.0
    # Auto-complete fon vazifasi (auction_closer kabi, testda o'chiq).
    auto_complete_enabled: bool = False
    auto_complete_interval_seconds: int = 300

    # Redis (token blacklist, keyin kesh/pub-sub). Bo'sh bo'lsa in-memory fallback.
    redis_url: str = "redis://localhost:6379/0"
    # Frontend (Next.js) origin'lari — brauzerdan API'ga so'rov yuborishi uchun CORS.
    # .env orqali JSON ro'yxat sifatida beriladi: CORS_ORIGINS='["https://bazart.uz"]'
    cors_origins: list[str] = ["http://localhost:3000"]

    # Celery (fon vazifalari: auksion yopish, auto-complete, push, email).
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
    def allow_mock_payments(self) -> bool:
        """Mock to'lov oqimiga ruxsat berilganmi.

        Faqat local/test. Prod'da mock provayder doim PAID qaytargani uchun
        bu bayroq yoqilsa istalgan xaridor tovarni to'lovsiz oladi.
        """
        return self.environment in _MOCK_SAFE_ENVIRONMENTS

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
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
