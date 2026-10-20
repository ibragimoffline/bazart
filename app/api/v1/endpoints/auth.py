from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.auth_cookie import (
    clear_refresh_cookie,
    read_refresh_cookie,
    require_trusted_origin,
    set_refresh_cookie,
)
from app.core.config import settings
from app.core.dependencies import (
    CurrentActiveUser,
    CurrentUser,
    DbSession,
    LoginForm,
    OptionalUser,
    optional_oauth2_scheme,
)
from app.core.rate_limit import RateLimiter
from app.models.enums import OtpPurpose
from app.models.user import User
from app.schemas.auth import (
    AccessToken,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LogoutRequest,
    MessageResponse,
    OtpRequestIn,
    OtpRequestResponse,
    OtpVerifyIn,
    OtpVerifyResponse,
    PasswordResetTokenResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    UserCreate,
    UserRead,
    VerificationTokenResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService, SessionTokens
from app.services.otp_service import OtpService

router = APIRouter()

OptionalBearerToken = Annotated[str | None, Depends(optional_oauth2_scheme)]


def _session_response(response: Response, tokens: SessionTokens) -> AccessToken:
    """Refresh — HttpOnly cookie'ga, access — tanaga. Ikki login yo'li ham shu orqali."""
    set_refresh_cookie(response, tokens.refresh_token, tokens.refresh_expires_at)
    return AccessToken(
        access_token=tokens.access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


def _client_ip(request: Request) -> str | None:
    """So'rov kelgan mijoz IP'sini aniqlaydi (kunlik IP limiti uchun).

    Reverse proxy ortida `X-Forwarded-For` dagi BIRINCHI IP asl mijoz bo'ladi.
    OGOHLANTIRISH: XFF mijoz tomonidan soxtalashtirilishi mumkin — faqat
    ishonchli proxy ortida ishonchli (rate_limit._identifier bilan bir xil naqsh).
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip
    if request.client is not None and request.client.host:
        return request.client.host
    return None


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter("auth", 60))],
)
def register(payload: UserCreate, db: DbSession) -> User:
    return AuthService(db).register_user(payload)


@router.post(
    "/login",
    response_model=AccessToken,
    dependencies=[Depends(RateLimiter("login", 60))],
)
def login(form_data: LoginForm, response: Response, db: DbSession) -> AccessToken:
    tokens = AuthService(db).login_user(form_data.username, form_data.password)
    return _session_response(response, tokens)


@router.post(
    "/google",
    response_model=AccessToken,
    dependencies=[Depends(RateLimiter("login", 60))],
)
def login_with_google(
    payload: GoogleLoginRequest, response: Response, db: DbSession
) -> AccessToken:
    tokens = AuthService(db).login_with_google(payload.credential)
    return _session_response(response, tokens)


@router.get("/me", response_model=UserRead)
def read_me(current_user: CurrentUser) -> User:
    return current_user


@router.post(
    "/refresh",
    response_model=AccessToken,
    dependencies=[Depends(require_trusted_origin)],
)
def refresh_token(
    request: Request,
    response: Response,
    db: DbSession,
    payload: RefreshTokenRequest | None = None,
) -> AccessToken | JSONResponse:
    """Refresh cookie bilan yangi access token (rotation). Body — faqat eski klientlar.

    401 = sessiya tugagan (muddati o'tgan, bekor qilingan, qayta ishlatilgan) — klient
    shundagina foydalanuvchini chiqaradi. Bunda cookie ham tozalanadi.
    """
    token = read_refresh_cookie(request) or (payload.refresh_token if payload else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    try:
        tokens = AuthService(db).refresh_session(token)
    except HTTPException as exc:
        failed = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        clear_refresh_cookie(failed)
        return failed
    return _session_response(response, tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def logout(
    request: Request,
    response: Response,
    token: OptionalBearerToken,
    db: DbSession,
    payload: LogoutRequest | None = None,
) -> MessageResponse:
    """Access token shart EMAS: u eskirgan bo'lsa ham refresh sessiya yopilishi kerak."""
    refresh = read_refresh_cookie(request) or (payload.refresh_token if payload else None)
    AuthService(db).logout_user(access_token=token, refresh_token=refresh)
    clear_refresh_cookie(response)
    return MessageResponse(message="Logged out")


@router.post(
    "/forgot-password",
    response_model=PasswordResetTokenResponse,
    dependencies=[Depends(RateLimiter("auth", 60))],
)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: DbSession,
) -> PasswordResetTokenResponse:
    # Token EMAIL orqali yuboriladi (TODO). Prod'da javobda QAYTARILMAYDI —
    # aks holda hujumchi istalgan email uchun reset token olib, akkauntni
    # egallaydi (security review KRITIK topilmasi). Local/test'da qaytariladi.
    reset_token = AuthService(db).create_password_reset_token_for_email(payload.email)
    return PasswordResetTokenResponse(
        message="If the email exists, password reset instructions have been generated",
        reset_token=None if settings.is_production else reset_token,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    dependencies=[Depends(RateLimiter("auth", 60))],
)
def reset_password(payload: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    AuthService(db).reset_password(payload.token, payload.new_password)
    return MessageResponse(message="Password has been reset")


@router.post("/verification-token", response_model=VerificationTokenResponse)
def generate_verification_token(
    current_user: CurrentActiveUser,
    db: DbSession,
) -> VerificationTokenResponse:
    token = AuthService(db).create_email_verification_token_for_user(current_user)
    return VerificationTokenResponse(
        message="Email verification token generated",
        verification_token=token,
    )


@router.post("/verify-email", response_model=UserRead)
def verify_email(payload: VerifyEmailRequest, db: DbSession) -> User:
    return AuthService(db).verify_email(payload.token)


@router.post(
    "/otp/request",
    response_model=OtpRequestResponse,
    dependencies=[Depends(RateLimiter("auth", 60))],
)
def request_otp(
    payload: OtpRequestIn,
    request: Request,
    db: DbSession,
) -> OtpRequestResponse:
    otp, code = OtpService(db).request_otp(payload.phone, payload.purpose, ip=_client_ip(request))
    # Xom kod FAQAT non-prod muhitda qaytariladi (test/local qulayligi uchun).
    # Prod'da kod faqat SMS orqali ketadi — javobda hech qachon oshkor bo'lmaydi.
    debug_code = None if settings.is_production else code
    return OtpRequestResponse(
        message="Tasdiqlash kodi yuborildi",
        expires_at=otp.expires_at,
        debug_code=debug_code,
    )


@router.post(
    "/otp/verify",
    response_model=OtpVerifyResponse,
    dependencies=[Depends(RateLimiter("auth", 60))],
)
def verify_otp(
    payload: OtpVerifyIn, db: DbSession, current_user: OptionalUser
) -> OtpVerifyResponse:
    OtpService(db).verify_otp(payload.phone, payload.code, payload.purpose)
    phone_verified = False
    if payload.purpose == OtpPurpose.PHONE_VERIFY:
        phone_verified = AuthService(db).mark_phone_verified(payload.phone, current_user)
    return OtpVerifyResponse(
        message="Kod tasdiqlandi",
        verified=True,
        phone_verified=phone_verified,
    )
