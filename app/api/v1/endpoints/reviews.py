"""Ikki tomonlama sharh + sotuvchi reytingi endpointlari.

Deal COMPLETED bo'lgach ishtirokchilar bir-birini baholaydi (1-5 yulduz).
Har sharh qabul qiluvchining `seller_rating`/`seller_rating_count`ini yangilaydi.
"""

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.review import ReviewCreate, ReviewRead
from app.services.review_service import ReviewService

router = APIRouter()


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_review(
    payload: ReviewCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> ReviewRead:
    review = ReviewService(db).create_review(
        deal_id=payload.deal_id,
        author=current_user,
        stars=payload.stars,
        text=payload.text,
    )
    return ReviewRead.model_validate(review)


@router.get("/user/{user_id}", response_model=list[ReviewRead])
def list_user_reviews(
    user_id: int,
    db: DbSession,
) -> list[ReviewRead]:
    reviews = ReviewService(db).list_for_user(user_id)
    return [ReviewRead.model_validate(r) for r in reviews]
