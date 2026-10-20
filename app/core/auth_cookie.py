"""Refresh token cookie'si va cookie-endpointlar uchun CSRF himoyasi.

Refresh token faqat HttpOnly cookie'da yuradi: XSS bo'lsa ham JS uni o'qiy olmaydi.
Cookie'ni brauzer avtomatik yuboradi — shuning uchun cookie bilan ishlaydigan
endpointlar (`/auth/refresh`, `/auth/logout`) begona saytdan chaqirilmasligi kerak:
SameSite=Lax asosiy to'siq, `Origin` tekshiruvi — ikkinchi qatlam.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, Request, Response, status

from app.core.config import settings


def set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    # Bazadan kelgan vaqt sessiya timezone'ida bo'lishi mumkin — cookie `Expires` faqat UTC.
    expires_at = expires_at.astimezone(UTC)
    max_age = max(0, int((expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=max_age,
        expires=expires_at,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain or None,
        secure=settings.refresh_cookie_secure_effective,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain or None,
        secure=settings.refresh_cookie_secure_effective,
        httponly=True,
        samesite=settings.refresh_cookie_samesite,
    )


def read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(settings.refresh_cookie_name) or None


def require_trusted_origin(request: Request) -> None:
    """Brauzer yuborgan `Origin` CORS ro'yxatida bo'lmasa — 403.

    Origin'siz so'rov (curl, server-server) CSRF vektori emas — u begona sayt nomidan
    foydalanuvchi cookie'sini yubora olmaydi, shuning uchun o'tkaziladi.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origins:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")
