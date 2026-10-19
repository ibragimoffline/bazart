"""Faza E2.9: deals.cancelled_at (bekor qilish cheklovi oynasi uchun)

Mavjud bekor qilingan kelishuvlarda `updated_at` (UTC, timezone'siz) olinadi.

Revision ID: 202610200033
Revises: 202610200032
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200033"
down_revision: str | None = "202610200032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE deals SET cancelled_at = updated_at AT TIME ZONE 'UTC' WHERE status = 'CANCELLED'"
    )


def downgrade() -> None:
    op.drop_column("deals", "cancelled_at")
