from fastapi import APIRouter, Depends, Request, status

from app.core.config import settings
from app.core.dependencies import (
    BearerToken,
    CurrentActiveUser,
    CurrentUser,
    DbSession,
    LoginForm,
    OptionalUser,
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
    Token,
    UserCreate,
    UserRead,
    VerificationTokenResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService
from app.services.otp_service import OtpService

router = APIRouter()


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
    response_model=Token,
    dependencies=[Depends(RateLimiter("login", 60))],
)
def login(form_data: LoginForm, db: DbSession) -> Token:
    return AuthService(db).login_user(form_data.username, form_data.password)


@router.post(
    "/google",
    response_model=Token,
    dependencies=[Depends(RateLimiter("login", 60))],
)
def login_with_google(payload: GoogleLoginRequest, db: DbSession) -> Token:
    return AuthService(db).login_with_google(payload.credential)


@router.get("/me", response_model=UserRead)
def read_me(current_user: CurrentUser) -> User:
    return current_user


@router.post("/refresh", response_model=AccessToken)
def refresh_token(payload: RefreshTokenRequest, db: DbSession) -> AccessToken:
    return AuthService(db).refresh_access_token(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: LogoutRequest, token: BearerToken, db: DbSession) -> MessageResponse:
    AuthService(db).logout_user(access_token=token, refresh_token=payload.refresh_token)
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
