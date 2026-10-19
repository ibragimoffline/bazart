"""narx tushdi xabarlari: notification_type.PRICE_DROPPED + auctions.last_price_alert

Revision ID: 202610190027
Revises: 202610190026
Create Date: 2026-10-19 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610190027"
down_revision: str | None = "202610190026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Yangi enum qiymati bu migratsiyada ishlatilmaydi — tranzaksiyada xavfsiz.
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'PRICE_DROPPED'")
    op.add_column("auctions", sa.Column("last_price_alert", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("auctions", "last_price_alert")
    # notification_type.PRICE_DROPPED qoladi (Postgres enum qiymatini o'chirib bo'lmaydi).
