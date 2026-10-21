from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import OtpPurpose
from app.schemas.user import UserCreate, UserRead
from app.schemas.user import normalize_phone as _normalize_phone


class AccessToken(BaseModel):
    """Login / Google / refresh javobi. Refresh token tanada EMAS — HttpOnly cookie'da."""

    access_token: str
    token_type: str = "bearer"
    # Access token umri (soniya) — klient muddatidan oldin jimgina yangilaydi.
    expires_in: int


class RefreshTokenRequest(BaseModel):
    """Faqat eski klientlar uchun (refresh token localStorage'da edi). Odatda — cookie."""

    refresh_token: str | None = None


class GoogleLoginRequest(BaseModel):
    """Google Identity Services bergan ID token (`credential`)."""

    credential: str = Field(min_length=1, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class PasswordResetTokenResponse(MessageResponse):
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(character.isalpha() for character in value):
            raise ValueError("Password must contain at least one letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one number")
        return value


class VerificationTokenResponse(MessageResponse):
    verification_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class OtpRequestIn(BaseModel):
    """Telefon tasdiqlash kodi so'rash (login qilgan foydalanuvchi uchun).

    `password` — faqat TASDIQLANGAN raqamni almashtirishda (qayta autentifikatsiya; Google
    foydalanuvchisi o'rniga yaqinda login qilgan bo'lishi mumkin). `purpose` eski klientlar
    uchun qoldirilgan — faqat `phone_verify` qo'llab-quvvatlanadi.
    """

    phone: str = Field(max_length=40)
    purpose: OtpPurpose = OtpPurpose.PHONE_VERIFY
    password: str | None = Field(default=None, max_length=128)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return _normalize_phone(value)


class OtpVerifyIn(BaseModel):
    """OTP kod tekshirish: telefon raqam + kod + maqsad."""

    phone: str = Field(max_length=40)
    code: str = Field(pattern=r"^\d{4,8}$")
    purpose: OtpPurpose = OtpPurpose.PHONE_VERIFY

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return _normalize_phone(value)


class OtpRequestResponse(MessageResponse):
    """OTP so'rash javobi. `debug_code` FAQAT non-prod muhitda to'ldiriladi.

    Prod'da kod hech qachon javobda qaytmaydi (aks holda SMS'siz ham kodni
    olib bo'lardi) — u faqat SMS orqali yetkaziladi.
    """

    expires_at: datetime
    # Shuncha soniyadan keyin qayta yuborish mumkin (UI taymeri uchun).
    resend_after_seconds: int
    debug_code: str | None = None


class OtpVerifyResponse(MessageResponse):
    verified: bool
    phone_verified: bool = False


__all__ = [
    "AccessToken",
    "ForgotPasswordRequest",
    "GoogleLoginRequest",
    "LogoutRequest",
    "MessageResponse",
    "OtpRequestIn",
    "OtpRequestResponse",
    "OtpVerifyIn",
    "OtpVerifyResponse",
    "PasswordResetTokenResponse",
    "RefreshTokenRequest",
    "ResetPasswordRequest",
    "UserCreate",
    "UserRead",
    "VerificationTokenResponse",
    "VerifyEmailRequest",
]
