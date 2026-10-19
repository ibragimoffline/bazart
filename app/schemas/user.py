import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole


def normalize_phone(value: str) -> str:
    """Telefon raqamdan bo'shliq/ajratgichlarni olib tashlaydi va tekshiradi.

    Kirish shakli erkin ("+998 90 123 45 67", "998901234567") bo'lishi mumkin —
    saqlash va taqqoslash uchun yagona ko'rinishga keltiriladi. Profil va OTP
    BIR XIL funksiyadan o'tadi: aks holda OTP tasdig'i saqlangan raqamni
    topolmay, telefon hech qachon tasdiqlanmaydi.
    """
    cleaned = value.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    digits = cleaned[1:] if cleaned.startswith("+") else cleaned
    if not digits.isdigit() or not (7 <= len(digits) <= 15):
        raise ValueError("Telefon raqam noto'g'ri formatda")
    return cleaned


_TELEGRAM_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def normalize_telegram_username(value: str) -> str:
    """Telegram nomi: boshidagi @ va t.me/ olib tashlanadi; Telegram qoidasi (5-32 belgi)."""
    cleaned = value.strip().removeprefix("https://").removeprefix("t.me/").removeprefix("@")
    if not _TELEGRAM_USERNAME.match(cleaned):
        raise ValueError("Telegram nomi noto'g'ri (5-32 belgi: harf, raqam, _)")
    return cleaned


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(character.isalpha() for character in value):
            raise ValueError("Password must contain at least one letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one number")
        return value


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    bio: str | None = Field(default=None, max_length=500)
    avatar_url: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=160)
    telegram_username: str | None = Field(default=None, max_length=64)

    @field_validator("telegram_username")
    @classmethod
    def validate_telegram_username(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_telegram_username(value)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        # Bo'sh satr = raqamni o'chirish.
        if value is None or not value.strip():
            return None
        return normalize_phone(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    phone: str | None
    bio: str | None
    avatar_url: str | None
    location: str | None
    telegram_username: str | None = None
    seller_rating: float
    seller_rating_count: int
    is_active: bool
    is_verified: bool
    role: UserRole
    created_at: datetime
    updated_at: datetime


class UserMeRead(UserRead):
    """Faqat foydalanuvchining o'ziga qaytariladigan kengaytirilgan profil.

    `telegram_chat_id` — SHAXSIY kanal identifikatori; ommaviy `UserRead`da
    OSHKOR QILINMAYDI (faqat egaga). `preferred_language` interfeys tili.
    """

    telegram_chat_id: str | None
    preferred_language: str
    # Telefon OTP orqali tasdiqlangan vaqt (None = tasdiqlanmagan).
    phone_verified_at: datetime | None


class TelegramLink(BaseModel):
    """Foydalanuvchi Telegram chat'ini ulash so'rovi tanasi."""

    chat_id: str = Field(min_length=1, max_length=40)


class UserPreferencesUpdate(BaseModel):
    """Foydalanuvchi afzalliklari: interfeys tili (uz/ru)."""

    preferred_language: Literal["uz", "ru"]
