"""golland zaxirasi: auctions.dutch_fallback_floor, continued_as_auction_id

Revision ID: 202610190026
Revises: 202610190025
Create Date: 2026-10-19 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610190026"
down_revision: str | None = "202610190025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Yangi bildirishnoma turi (bu migratsiyada ishlatilmaydi — tranzaksiyada xavfsiz).
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'DUTCH_STARTED'")

    op.add_column("auctions", sa.Column("dutch_fallback_floor", sa.BigInteger(), nullable=True))
    op.add_column("auctions", sa.Column("continued_as_auction_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_auctions_continued_as_auction_id",
        "auctions",
        "auctions",
        ["continued_as_auction_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "auctions_continued_as_auction_id_key", "auctions", ["continued_as_auction_id"]
    )
    op.create_check_constraint(
        "ck_auctions_dutch_fallback",
        "auctions",
        "dutch_fallback_floor IS NULL OR (pricing_mode = 'ASCENDING' AND dutch_fallback_floor > 0)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_auctions_dutch_fallback", "auctions", type_="check")
    op.drop_constraint("auctions_continued_as_auction_id_key", "auctions", type_="unique")
    op.drop_constraint("fk_auctions_continued_as_auction_id", "auctions", type_="foreignkey")
    op.drop_column("auctions", "continued_as_auction_id")
    op.drop_column("auctions", "dutch_fallback_floor")
    # notification_type.DUTCH_STARTED qoladi (Postgres enum qiymatini o'chirib bo'lmaydi).
