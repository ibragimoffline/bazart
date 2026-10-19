from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import DealStatus
from app.models.review import Review
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.repositories.review_repository import ReviewRepository
from app.repositories.user_repository import UserRepository


class ReviewService:
    """Ikki tomonlama sharh + sotuvchi reytingi.

    Deal COMPLETED bo'lgach xaridor va sotuvchi bir-birini baholaydi
    (1-5 yulduz). Har sharhdan keyin qabul qiluvchining `seller_rating`
    (o'rtacha) va `seller_rating_count` UNGA kelgan barcha sharhlardan
    qayta hisoblanadi — bitta izchil tranzaksiyada.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.reviews = ReviewRepository(db)
        self.deals = DealRepository(db)
        self.users = UserRepository(db)

    def create_review(
        self, deal_id: int, author: User, stars: int, text: str | None = None
    ) -> Review:
        """Deal ishtirokchisi ikkinchi tomonni baholaydi.

        Shartlar: deal mavjud, COMPLETED (aks holda 400), muallif deal
        ishtirokchisi (buyer/seller, aks holda 403), shu deal+muallif uchun
        sharh hali yo'q (aks holda 409). `to_id` — orderning ikkinchi tomoni;
        o'ziga sharh imkonsiz (ishtirokchi tekshiruvidan kelib chiqadi).
        """
        deal = self.deals.get(deal_id)
        if deal is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

        if author.id not in {deal.buyer_id, deal.seller_id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your deal")

        if deal.status != DealStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deal COMPLETED holatida emas",
            )

        # Muallif buyer bo'lsa -> sotuvchini, sotuvchi bo'lsa -> xaridorni baholaydi.
        to_id = deal.seller_id if author.id == deal.buyer_id else deal.buyer_id

        existing = self.reviews.get_by_order_and_author(deal_id, author.id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu deal uchun sharh allaqachon qoldirilgan",
            )

        review = Review(
            deal_id=deal_id,
            from_id=author.id,
            to_id=to_id,
            stars=stars,
            text=text,
        )
        self.reviews.create(review)  # flush — reytingni shu sharh bilan hisoblash uchun

        self._recompute_rating(to_id)

        self.db.commit()
        self.db.refresh(review)
        return review

    def _recompute_rating(self, to_id: int) -> None:
        """Qabul qiluvchining reytingini UNGA kelgan barcha sharhlardan qayta hisoblaydi.

        AVG(stars) `Numeric(3,2)` ustuniga aniq yaxlitlanadi (ROUND_HALF_UP,
        2 kasr). Float TAQIQ — Decimal orqali. Commit chaqiruvchida.
        """
        user = self.users.get_by_id(to_id)
        if user is None:
            return

        count, avg = self.reviews.aggregate_for_user(to_id)
        if count == 0 or avg is None:
            user.seller_rating = Decimal("0.00")
            user.seller_rating_count = 0
        else:
            # str() orqali: avg Postgres'da Decimal, ammo float kelsa ham aniq.
            user.seller_rating = Decimal(str(avg)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            user.seller_rating_count = count
        self.db.add(user)
        self.db.flush()

    def list_for_user(self, user_id: int) -> list[Review]:
        """Foydalanuvchiga kelgan barcha sharhlar."""
        return self.reviews.list_for_user(user_id)
