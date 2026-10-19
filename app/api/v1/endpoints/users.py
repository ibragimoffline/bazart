from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, DbSession
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    PublicProfile,
    TelegramLink,
    UserMeRead,
    UserPreferencesUpdate,
    UserRead,
    UserUpdate,
)
from app.services.trust_service import TrustService

router = APIRouter()


@router.get("/me", response_model=UserMeRead)
def read_profile(current_user: CurrentUser) -> User:
    # Egaga o'zining shaxsiy maydonlari (telegram_chat_id, til) ham qaytadi.
    return current_user


@router.patch("/me", response_model=UserRead)
def update_profile(payload: UserUpdate, current_user: CurrentUser, db: DbSession) -> User:
    return UserRepository(db).update(current_user, payload)


@router.post("/me/telegram", response_model=UserMeRead)
def link_telegram(payload: TelegramLink, current_user: CurrentUser, db: DbSession) -> User:
    """Autentifikatsiyalangan foydalanuvchi o'z Telegram chat'ini ulaydi.

    Faqat o'ziga: `current_user` orqali — begona chat_id boshqa akkauntga
    biriktirilmaydi. Ulangach, bildirishnomalar shu chat'ga ham yetkaziladi.
    """
    current_user.telegram_chat_id = payload.chat_id
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/preferences", response_model=UserMeRead)
def update_preferences(
    payload: UserPreferencesUpdate, current_user: CurrentUser, db: DbSession
) -> User:
    """Foydalanuvchi interfeys tilini (uz/ru) yangilaydi — faqat o'ziniki."""
    current_user.preferred_language = payload.preferred_language
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}/profile", response_model=PublicProfile)
def read_public_profile(user_id: int, db: DbSession) -> PublicProfile:
    """Ommaviy profil: reyting va kelishuv hisoblagichlari. Kontaktsiz; o'chirilgan yoki
    bloklangan foydalanuvchi — 404."""
    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    stats = TrustService(db).stats(user.id)
    return PublicProfile(
        id=user.id,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        location=user.location,
        seller_rating=float(user.seller_rating),
        seller_rating_count=user.seller_rating_count,
        created_at=user.created_at,
        deals_completed=stats.deals_completed,
        cancelled_as_buyer=stats.cancelled_as_buyer,
        cancelled_as_seller=stats.cancelled_as_seller,
    )
