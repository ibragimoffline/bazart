"""auctions.ending_soon_notified_at + items.relisted_from_id

Revision ID: 202610170022
Revises: 202610130021
Create Date: 2026-10-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610170022"
down_revision: str | None = "202610130021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auctions",
        sa.Column("ending_soon_notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("items", sa.Column("relisted_from_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_items_relisted_from_id_items", "items", "items", ["relisted_from_id"], ["id"]
    )
    op.create_unique_constraint("uq_items_relisted_from_id", "items", ["relisted_from_id"])


def downgrade() -> None:
    op.drop_constraint("uq_items_relisted_from_id", "items", type_="unique")
    op.drop_constraint("fk_items_relisted_from_id_items", "items", type_="foreignkey")
    op.drop_column("items", "relisted_from_id")
    op.drop_column("auctions", "ending_soon_notified_at")
