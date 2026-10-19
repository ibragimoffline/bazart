from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auction import Auction
from app.models.bid import Bid
from app.models.enums import AuctionStatus, ItemStatus, ListingType, OrderStatus, UserRole
from app.models.item import Item
from app.models.order import Order
from app.models.user import User
from app.services.auction_service import AuctionService
from app.services.offer_service import OfferService


class AdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_users(
        self,
        *,
        search: str | None = None,
        role: UserRole | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        statement = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                (User.email.ilike(pattern)) | (User.full_name.ilike(pattern))
            )
        if role is not None:
            statement = statement.where(User.role == role)
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        return list(self.db.scalars(statement))

    def block_user(self, user_id: int, actor: User) -> User:
        user = self._get_user_or_404(user_id)
        self._guard_privileged_target(user, actor, action="block")
        user.is_active = False
        return self._save_user(user)

    def unblock_user(self, user_id: int, actor: User) -> User:
        user = self._get_user_or_404(user_id)
        self._guard_privileged_target(user, actor, action="unblock")
        user.is_active = True
        return self._save_user(user)

    def change_user_role(self, user_id: int, role: UserRole, actor: User) -> User:
        """Rolni o'zgartiradi. Faqat superadmin chaqiradi (endpoint darajasida).

        Guard: hech kim o'z rolini o'zgartira olmaydi (o'zini qulflab qo'yish
        yoki tasodifan huquqni yo'qotishning oldini oladi).
        """
        user = self._get_user_or_404(user_id)
        if user.id == actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change your own role",
            )
        user.role = role
        return self._save_user(user)

    @staticmethod
    def _guard_privileged_target(target: User, actor: User, *, action: str) -> None:
        """Admin/superadminni bloklashdan himoya qiladi.

        - hech kim o'zini bloklamaydi;
        - superadmin umuman bloklanmaydi (platformaning eng yuqori huquqi);
        - oddiy admin boshqa admin/superadminni bloklay olmaydi — faqat superadmin.
        """
        if target.id == actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot {action} yourself",
            )
        if target.role == UserRole.SUPERADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superadmin cannot be blocked",
            )
        if target.role == UserRole.ADMIN and actor.role != UserRole.SUPERADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only a superadmin can block an admin",
            )

    def list_items(
        self,
        *,
        search: str | None = None,
        status_filter: ItemStatus | None = None,
        seller_id: int | None = None,
        category_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Item]:
        statement = select(Item).order_by(Item.created_at.desc()).offset(skip).limit(limit)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                (Item.title.ilike(pattern)) | (Item.description.ilike(pattern))
            )
        if status_filter is not None:
            statement = statement.where(Item.status == status_filter)
        if seller_id is not None:
            statement = statement.where(Item.seller_id == seller_id)
        if category_id is not None:
            statement = statement.where(Item.category_id == category_id)
        return list(self.db.scalars(statement))

    def approve_item(self, item_id: int) -> Item:
        item = self._get_item_or_404(item_id)
        item.status = ItemStatus.ACTIVE
        return self._save_item(item)

    def reject_item(self, item_id: int) -> Item:
        """Moderatsiya: e'lonni rad etadi.

        Jonli auksion bo'lsa u ham bekor qilinadi — aks holda rad etilgan e'lon
        bid qabul qilishda davom etar, taklifsiz tugasa esa sotuvchi uni qayta
        joylab moderatsiyani chetlab o'tardi.
        """
        item = self._get_item_or_404(item_id)
        if item.listing_type == ListingType.OFFER and item.status != ItemStatus.SOLD:
            # Ochiq takliflar ham yopiladi; CANCELLED e'lonni sotuvchi qayta ocholmaydi
            # (publish faqat EXPIRED'ni qayta ochadi) — moderatsiyani chetlab bo'lmaydi.
            return OfferService(self.db).cancel_listing(item.id)
        auction = item.auction
        if auction is not None and auction.status in (
            AuctionStatus.SCHEDULED,
            AuctionStatus.ACTIVE,
        ):
            AuctionService(self.db).cancel_as_admin(auction.id)
            self.db.refresh(item)
            return item
        item.status = ItemStatus.CANCELLED
        return self._save_item(item)

    def list_auctions(
        self,
        *,
        status_filter: AuctionStatus | None = None,
        seller_id: int | None = None,
        item_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Auction]:
        statement = select(Auction).order_by(Auction.end_time.asc()).offset(skip).limit(limit)
        if status_filter is not None:
            statement = statement.where(Auction.status == status_filter)
        if seller_id is not None:
            statement = statement.where(Auction.seller_id == seller_id)
        if item_id is not None:
            statement = statement.where(Auction.item_id == item_id)
        return list(self.db.scalars(statement))

    def cancel_auction(self, auction_id: int) -> Auction:
        # Qulf + state machine + tovarni ham bekor qilish — AuctionService'da.
        return AuctionService(self.db).cancel_as_admin(auction_id)

    def list_bids(
        self,
        *,
        auction_id: int | None = None,
        bidder_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Bid]:
        statement = select(Bid).order_by(Bid.created_at.desc()).offset(skip).limit(limit)
        if auction_id is not None:
            statement = statement.where(Bid.auction_id == auction_id)
        if bidder_id is not None:
            statement = statement.where(Bid.bidder_id == bidder_id)
        return list(self.db.scalars(statement))

    def list_orders(
        self,
        *,
        status_filter: OrderStatus | None = None,
        buyer_id: int | None = None,
        seller_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Order]:
        statement = select(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit)
        if status_filter is not None:
            statement = statement.where(Order.status == status_filter)
        if buyer_id is not None:
            statement = statement.where(Order.buyer_id == buyer_id)
        if seller_id is not None:
            statement = statement.where(Order.seller_id == seller_id)
        return list(self.db.scalars(statement))

    def get_statistics(self) -> dict[str, int]:
        """Platforma statistikasi. total_sales_amount — tiyinda."""
        total_users = self.db.scalar(select(func.count(User.id))) or 0
        total_active_auctions = (
            self.db.scalar(
                select(func.count(Auction.id)).where(Auction.status == AuctionStatus.ACTIVE)
            )
            or 0
        )
        total_completed_orders = (
            self.db.scalar(
                select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED)
            )
            or 0
        )
        total_sales_amount = (
            self.db.scalar(
                select(func.coalesce(func.sum(Order.final_price), 0)).where(
                    Order.status.in_(
                        [OrderStatus.PAID, OrderStatus.PICKUP_PENDING, OrderStatus.COMPLETED]
                    )
                )
            )
            or 0
        )
        # Pul tiyinda (butun son) — yaxlitlash kerak emas.
        total_sales_amount = int(total_sales_amount)
        return {
            "total_users": total_users,
            "total_active_auctions": total_active_auctions,
            "total_completed_orders": total_completed_orders,
            "total_sales_amount": total_sales_amount,
        }

    def _get_user_or_404(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    def _get_item_or_404(self, item_id: int) -> Item:
        item = self.db.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        return item

    def _save_user(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _save_item(self, item: Item) -> Item:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
