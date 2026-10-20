"""Faza E2.10: next_bidder_offers.expired_at (muddat o'tishini qayd etuvchi fon vazifasi)

Revision ID: 202610200036
Revises: 202610200035
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200036"
down_revision: str | None = "202610200035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "next_bidder_offers", sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("next_bidder_offers", "expired_at")
