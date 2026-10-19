from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.deal import Deal


class DealRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, deal_id: int) -> Deal | None:
        return self.db.get(Deal, deal_id)

    def get_by_auction_id(self, auction_id: int) -> Deal | None:
        statement = select(Deal).where(Deal.auction_id == auction_id)
        return self.db.scalar(statement)

    def add(self, deal: Deal) -> Deal:
        """Yangi kelishuvni qo'shadi (flush). COMMIT QILMAYDI — chaqiruvchi tranzaksiyasi."""
        self.db.add(deal)
        self.db.flush()
        return deal

    def list_for_buyer(self, buyer_id: int) -> list[Deal]:
        statement = select(Deal).where(Deal.buyer_id == buyer_id).order_by(Deal.created_at.desc())
        return list(self.db.scalars(statement))

    def list_for_seller(self, seller_id: int) -> list[Deal]:
        statement = select(Deal).where(Deal.seller_id == seller_id).order_by(Deal.created_at.desc())
        return list(self.db.scalars(statement))

    def list_all(self) -> list[Deal]:
        statement = select(Deal).order_by(Deal.created_at.desc())
        return list(self.db.scalars(statement))

    def get_for_update(self, deal_id: int) -> Deal | None:
        """Kelishuv qatorini FOR UPDATE bilan oladi: "Sotildi" va "Tasdiqlayman" bir vaqtda
        kelsa, ikkalasi bir-birining yozuvini ko'rmay qolib kelishuv `agreed` da qotmasin."""
        return self.db.scalar(select(Deal).where(Deal.id == deal_id).with_for_update())
