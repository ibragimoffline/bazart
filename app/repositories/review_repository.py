from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.review import Review


class ReviewRepository:
    """Sharh yozuvlariga DB kirishi (select/insert/aggregate)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, review: Review) -> Review:
        self.db.add(review)
        self.db.flush()
        return review

    def get_by_order_and_author(self, deal_id: int, from_id: int) -> Review | None:
        """Shu deal uchun shu muallif qoldirgan sharh (UNIQUE deal_id+from_id)."""
        statement = select(Review).where(
            Review.deal_id == deal_id,
            Review.from_id == from_id,
        )
        return self.db.scalar(statement)

    def list_for_user(self, to_id: int) -> list[Review]:
        """Foydalanuvchiga kelgan barcha sharhlar (yangi birinchi)."""
        statement = select(Review).where(Review.to_id == to_id).order_by(Review.created_at.desc())
        return list(self.db.scalars(statement))

    def aggregate_for_user(self, to_id: int) -> tuple[int, float | None]:
        """Foydalanuvchiga kelgan sharhlar bo'yicha (COUNT, AVG(stars)).

        AVG hech sharh bo'lmasa None qaytaradi — reyting hisobi buni 0 deb
        talqin qiladi.
        """
        statement = select(func.count(Review.id), func.avg(Review.stars)).where(
            Review.to_id == to_id
        )
        count, avg = self.db.execute(statement).one()
        return count, avg
