from pydantic import BaseModel

from app.models.enums import UserRole
from app.money.fields import TiyinAmount


class UserRoleUpdate(BaseModel):
    role: UserRole


class AdminStatsRead(BaseModel):
    total_users: int
    total_active_auctions: int
    total_completed_deals: int
    total_sales_amount: TiyinAmount
