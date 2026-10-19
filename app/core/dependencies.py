from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# Token ixtiyoriy bo'lgan endpointlar uchun (yo'q bo'lsa 401 emas, None).
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
BearerToken = Annotated[str, Depends(oauth2_scheme)]
LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]


def current_user(token: BearerToken, db: DbSession) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = UserRepository(db).get_by_id(int(subject))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def current_active_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return user


PHONE_VERIFICATION_REQUIRED = "phone_verification_required"


def current_verified_user(user: Annotated[User, Depends(current_active_user)]) -> User:
    """Telefoni tasdiqlangan faol foydalanuvchi (Faza E2.1).

    Bid, taklif, e'lon va xarid kelishuvga olib keladi; kelishuvda ikkinchi tomonga telefon
    ochiladi. Shu sababli raqam OTP bilan tasdiqlangan bo'lishi shart — tasdiqlanmagan
    raqam ochilsa, u soxta yoki begona bo'lishi mumkin.
    """
    if user.phone is None or user.phone_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PHONE_VERIFICATION_REQUIRED,
        )
    return user


def optional_current_user(
    token: Annotated[str | None, Depends(optional_oauth2_scheme)], db: DbSession
) -> User | None:
    """Token bo'lsa — foydalanuvchi, bo'lmasa yoki yaroqsiz bo'lsa — None."""
    if not token:
        return None
    payload = decode_access_token(token)
    subject = payload.get("sub") if payload else None
    if subject is None:
        return None
    user = UserRepository(db).get_by_id(int(subject))
    return user if user is not None and user.is_active else None


# Superadmin — adminning ustki to'plami: admin talab qilingan hamma joyga o'tadi.
_ADMIN_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)


def current_admin_user(user: Annotated[User, Depends(current_active_user)]) -> User:
    if user.role not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


def current_superadmin_user(user: Annotated[User, Depends(current_active_user)]) -> User:
    """Faqat superadmin: rol berish, adminlarni bloklash kabi sezgir amallar uchun."""
    if user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privileges required",
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]
CurrentActiveUser = Annotated[User, Depends(current_active_user)]
CurrentVerifiedUser = Annotated[User, Depends(current_verified_user)]
OptionalUser = Annotated[User | None, Depends(optional_current_user)]
CurrentAdminUser = Annotated[User, Depends(current_admin_user)]
CurrentSuperAdminUser = Annotated[User, Depends(current_superadmin_user)]


def require_roles(*allowed_roles: UserRole):
    def dependency(user: CurrentActiveUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


CurrentSeller = Annotated[
    User, Depends(require_roles(UserRole.SELLER, UserRole.ADMIN, UserRole.SUPERADMIN))
]
CurrentAdmin = CurrentAdminUser
CurrentSuperAdmin = CurrentSuperAdminUser
