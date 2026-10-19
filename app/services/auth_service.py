from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    EMAIL_VERIFICATION_TOKEN_TYPE,
    PASSWORD_RESET_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AccessToken, Token, UserCreate
from app.services.google_identity import verify_google_id_token


def _send_email(to: str, subject: str, body: str) -> None:
    """Emailni fon vazifasiga topshiradi (best-effort, so'rovni bloklamaydi).

    Lazy import — Celery'ni auth uchun majburiy bog'liqlik qilmaslik va aylanma
    importdan qochish uchun. Broker/worker yo'q bo'lsa enqueue() inline zaxira.
    """
    from app.tasks.dispatch import enqueue
    from app.tasks.email import send_email

    enqueue(send_email, to=to, subject=subject, body=body)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)

    def register_user(self, payload: UserCreate) -> User:
        # TODO: Add email verification, rate limiting, and audit logging before production.
        existing_user = self.users.get_by_email(payload.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )
        return self.users.create(payload)

    def login_user(self, email: str, password: str) -> Token:
        # TODO: Add refresh tokens, account lockout, and suspicious-login detection.
        user = self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return self._create_token_pair(user)

    def refresh_access_token(self, refresh_token: str) -> AccessToken:
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        user = self.users.get_by_id(int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        return AccessToken(access_token=create_access_token(subject=str(user.id)))

    def logout_user(self, access_token: str, refresh_token: str | None = None) -> None:
        revoke_token(access_token)
        if refresh_token is not None:
            revoke_token(refresh_token)

    def create_password_reset_token_for_email(self, email: str) -> str | None:
        user = self.users.get_by_email(email)
        if user is None:
            return None
        token = create_password_reset_token(subject=str(user.id))
        # Token EMAIL orqali yuboriladi — fon vazifasi (queue). Prod'da javobda
        # qaytarilmaydi (config.is_production), lekin har doim email jo'natiladi.
        _send_email(user.email, "Bazart — parolni tiklash", f"Parolni tiklash uchun token: {token}")
        return token

    def reset_password(self, token: str, new_password: str) -> None:
        payload = decode_token(token, expected_type=PASSWORD_RESET_TOKEN_TYPE)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token",
            )

        user = self.users.get_by_id(int(payload["sub"]))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password reset token",
            )
        self.users.update_password(user, new_password)
        revoke_token(token)

    def create_email_verification_token_for_user(self, user: User) -> str:
        token = create_email_verification_token(subject=str(user.id))
        _send_email(
            user.email, "Bazart — email tasdiqlash", f"Emailni tasdiqlash uchun token: {token}"
        )
        return token

    def verify_email(self, token: str) -> User:
        payload = decode_token(token, expected_type=EMAIL_VERIFICATION_TOKEN_TYPE)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email verification token",
            )

        user = self.users.get_by_id(int(payload["sub"]))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email verification token",
            )
        verified_user = self.users.mark_verified(user)
        revoke_token(token)
        return verified_user

    def mark_phone_verified(self, phone: str, user: User | None) -> bool:
        """Telefon OTP tasdig'idan keyin SO'ROVCHI foydalanuvchini tasdiqlangan deb belgilaydi.

        Ilgari raqam bo'yicha istalgan foydalanuvchi topilib belgilanardi: `phone` unique
        emas, ya'ni boshqa akkaunt shu raqamni profiliga yozib, egasining OTP'si bilan
        "tasdiqlangan" bo'lib qolishi mumkin edi. Faza E da tasdiqlangan raqam kelishuvda
        ikkinchi tomonga ochiladi, shuning uchun faqat tizimga kirgan va profilida aynan shu
        raqam turgan foydalanuvchi belgilanadi. Raqam boshqa akkauntda allaqachon
        tasdiqlangan bo'lsa — 409 (bitta raqam = bitta tasdiqlangan akkaunt).

        :return: so'rovchi tasdiqlangan bo'lsa True (anonim yoki raqam mos emas — False).
        """
        if user is None or user.phone != phone:
            return False
        taken = self.db.scalar(
            select(User.id).where(
                User.phone == phone, User.phone_verified_at.is_not(None), User.id != user.id
            )
        )
        if taken is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu raqam boshqa akkauntda tasdiqlangan",
            )
        if user.phone_verified_at is None:
            user.phone_verified_at = datetime.now(UTC)
            self.db.add(user)
            self.db.commit()
        return True

    def login_with_google(self, credential: str) -> Token:
        """Google ID token bilan kirish yoki ro'yxatdan o'tish (bitta oqim).

        Tartib: avval `google_sub` bo'yicha (email o'zgargan bo'lsa ham topiladi),
        keyin email bo'yicha mavjud akkauntga bog'lash, bo'lmasa yangi akkaunt.
        Email bo'yicha bog'lash FAQAT Google emailni tasdiqlagan bo'lsa — aks
        holda tasdiqlanmagan email orqali begona akkauntni egallash mumkin.
        """
        identity = verify_google_id_token(credential)

        user = self.users.get_by_google_sub(identity.sub)
        if user is None:
            if not identity.email_verified:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Google email is not verified",
                )
            user = self.users.get_by_email(identity.email)
            if user is None:
                user = self.users.create_from_google(
                    email=identity.email,
                    google_sub=identity.sub,
                    full_name=identity.name,
                    avatar_url=identity.picture,
                )
            else:
                # Tasdiqlanmagan akkauntni kimdir boshqa odamning emaili bilan
                # oldindan ochib qo'ygan bo'lishi mumkin (pre-hijack). Haqiqiy
                # egasi Google orqali kirganda o'sha begona parol bekor qilinadi.
                self.users.link_google(
                    user, google_sub=identity.sub, reset_password=not user.is_verified
                )

        if not user.is_active or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        return self._create_token_pair(user)

    def _create_token_pair(self, user: User) -> Token:
        return Token(
            access_token=create_access_token(subject=str(user.id)),
            refresh_token=create_refresh_token(subject=str(user.id)),
        )
