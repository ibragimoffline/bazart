import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    EMAIL_VERIFICATION_TOKEN_TYPE,
    PASSWORD_RESET_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_session_refresh_token,
    decode_token,
    revoke_token,
    verify_password,
)
from app.models.auth_session import AuthSession
from app.models.user import User
from app.repositories.auth_session_repository import AuthSessionRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserCreate
from app.schemas.user import UserUpdate
from app.services.google_identity import verify_google_id_token

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionTokens:
    """Kirish/refresh natijasi. Access — javob tanasida, refresh — faqat cookie'ga."""

    access_token: str
    refresh_token: str
    refresh_expires_at: datetime


def _invalid_refresh() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )


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
        self.sessions = AuthSessionRepository(db)

    def register_user(self, payload: UserCreate) -> User:
        # TODO: Add email verification, rate limiting, and audit logging before production.
        existing_user = self.users.get_by_email(payload.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )
        return self.users.create(payload)

    def login_user(self, email: str, password: str) -> SessionTokens:
        # TODO: account lockout va shubhali kirishni aniqlash.
        user = self.users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return self._start_session(user)

    def refresh_session(self, refresh_token: str) -> SessionTokens:
        """Refresh tokenni almashtiradi (rotation) va yangi access token beradi.

        Sessiya qatori `FOR UPDATE` bilan qulflanadi — bir vaqtda kelgan refresh'lar
        ketma-ket ko'riladi. Hozirgi jti -> yangi jti, muddat uzayadi (lekin
        `refresh_session_max_days` chegarasidan oshmaydi). Oldingi jti grace oynasida kelsa
        (parallel so'rov) — hozirgi token qayta beriladi, muddat UZAYMAYDI. Undan eski yoki
        oynadan tashqaridagi jti — o'g'irlangan token belgisi: sessiya bekor.
        """
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        if payload is None:
            raise _invalid_refresh()

        user = self.users.get_by_id(int(payload["sub"]))
        if user is None or not user.is_active or user.deleted_at is not None:
            raise _invalid_refresh()

        sid = payload.get("sid")
        if sid is None:
            # Cookie'dan oldingi token (localStorage'dan ko'chirish): bir martalik —
            # eski jti blacklist'ga tushadi, o'rniga sessiyali cookie beriladi.
            if not settings.legacy_refresh_body_enabled:
                raise _invalid_refresh()
            revoke_token(refresh_token)
            return self._start_session(user)

        try:
            session_id = uuid.UUID(str(sid))
        except ValueError:
            raise _invalid_refresh() from None

        session = self.sessions.get_for_update(session_id)
        now = datetime.now(UTC)
        if (
            session is None
            or session.user_id != user.id
            or session.revoked_at is not None
            or session.expires_at <= now
            or self._absolute_end(session) <= now
        ):
            self.db.rollback()
            raise _invalid_refresh()

        jti = payload.get("jti")
        if jti == session.current_jti:
            session.previous_jti = jti
            session.current_jti = str(uuid.uuid4())
            session.rotated_at = now
            session.expires_at = min(
                now + timedelta(days=settings.refresh_token_expire_days),
                self._absolute_end(session),
            )
        elif not self._within_grace(session, jti, now):
            self.sessions.revoke(session, "reuse")
            self.db.commit()
            logger.warning(
                "Refresh token qayta ishlatildi — sessiya bekor qilindi",
                extra={"auth_session_id": str(session.id), "user_id": user.id},
            )
            raise _invalid_refresh()

        tokens = self._issue(user, session)
        self.db.commit()
        return tokens

    def logout_user(self, access_token: str | None, refresh_token: str | None) -> None:
        """Access tokenni blacklist'ga, refresh sessiyani bekor qiladi.

        Access token muddati o'tgan bo'lsa ham logout ishlaydi — aks holda 30 daqiqadan
        keyin "Chiqish" refresh sessiyani ochiq qoldirardi.
        """
        if access_token:
            revoke_token(access_token)
        if not refresh_token:
            return
        payload = decode_token(refresh_token, expected_type=REFRESH_TOKEN_TYPE)
        if payload is None:
            return
        sid = payload.get("sid")
        if sid is None:
            revoke_token(refresh_token)
            return
        try:
            session = self.sessions.get(uuid.UUID(str(sid)))
        except ValueError:
            return
        if session is not None and str(session.user_id) == str(payload.get("sub")):
            self.sessions.revoke(session, "logout")
            self.db.commit()

    @staticmethod
    def _absolute_end(session: AuthSession) -> datetime:
        """Sirpanuvchi muddatdan qat'i nazar sessiya shu paytda tugaydi (qayta login)."""
        return session.created_at + timedelta(days=settings.refresh_session_max_days)

    @staticmethod
    def _within_grace(session: AuthSession, jti: str | None, now: datetime) -> bool:
        return (
            jti is not None
            and jti == session.previous_jti
            and session.rotated_at is not None
            and now - session.rotated_at <= timedelta(seconds=settings.refresh_reuse_grace_seconds)
        )

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
        # Parol tiklandi — boshqa qurilmalardagi (o'g'irlangan bo'lishi mumkin) sessiyalar yopiladi.
        self.sessions.revoke_all_for_user(user.id, "password_reset")
        self.db.commit()

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

    def update_profile(self, user: User, payload: UserUpdate) -> User:
        """Profilni yangilaydi. Tasdiqlangan raqam bu yerda almashtirilmaydi va o'chirilmaydi.

        Ilgari PATCH raqamni darhol yozib tasdiqni bekor qilardi: yangi raqam hali
        tasdiqlanmagan bo'lsa ham foydalanuvchi bid/taklifdan uzilardi, ochiq kelishuvda esa
        telefoni yo'qolardi. Endi almashtirish faqat OTP orqali (yangi raqam tasdiqlangandan
        keyin, qayta autentifikatsiya bilan) — `OtpService.verify_phone_code`.
        """
        data = payload.model_dump(exclude_unset=True)
        if "phone" in data and user.phone_verified_at is not None and data["phone"] != user.phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="phone_change_requires_verification",
            )
        return self.users.update(user, payload)

    def login_with_google(self, credential: str) -> SessionTokens:
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
        return self._start_session(user)

    def _start_session(self, user: User) -> SessionTokens:
        """Yangi refresh-sessiya. Email/parol va Google — bitta yo'l, bir xil umr."""
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        session = self.sessions.create(
            user_id=user.id, jti=str(uuid.uuid4()), expires_at=expires_at
        )
        tokens = self._issue(user, session)
        self.db.commit()
        return tokens

    @staticmethod
    def _issue(user: User, session: AuthSession) -> SessionTokens:
        return SessionTokens(
            access_token=create_access_token(subject=str(user.id), auth_time=session.created_at),
            refresh_token=create_session_refresh_token(
                subject=str(user.id),
                session_id=str(session.id),
                jti=session.current_jti,
                expires_at=session.expires_at,
            ),
            refresh_expires_at=session.expires_at,
        )
