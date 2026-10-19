"""Faza E2.3: kelishuv hayot sikli ustunlari

`deals` ga: `contacts_revealed_at`, `seller_marked_sold_at`, `buyer_confirmed_at`,
`completed_at`, `cancelled_by_id`, `cancel_reason` (`deal_cancel_reason` enum), `at_fault_id`.
Mavjud kelishuvlar `agreed` dan o'tgan, ya'ni kontaktlari ochiq: `contacts_revealed_at` =
`created_at`; yakunlanganlarda `completed_at` = `updated_at`.

Revision ID: 202610200031
Revises: 202610200030
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200031"
down_revision: str | None = "202610200030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANCEL_REASONS = ("NO_RESPONSE", "CHANGED_MIND", "NOT_AS_DESCRIBED", "OTHER")
_TS_COLUMNS = (
    "contacts_revealed_at",
    "seller_marked_sold_at",
    "buyer_confirmed_at",
    "completed_at",
)


def upgrade() -> None:
    reason = postgresql.ENUM(*CANCEL_REASONS, name="deal_cancel_reason", create_type=False)
    reason.create(op.get_bind(), checkfirst=False)

    for column in _TS_COLUMNS:
        op.add_column("deals", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "deals",
        sa.Column("cancelled_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("deals", sa.Column("cancel_reason", reason, nullable=True))
    op.add_column(
        "deals", sa.Column("at_fault_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)
    )

    # created_at/updated_at — timestamp without time zone, UTC da yozilgan.
    op.execute("UPDATE deals SET contacts_revealed_at = created_at AT TIME ZONE 'UTC'")
    op.execute(
        "UPDATE deals SET completed_at = updated_at AT TIME ZONE 'UTC' WHERE status = 'COMPLETED'"
    )


def downgrade() -> None:
    op.drop_column("deals", "at_fault_id")
    op.drop_column("deals", "cancel_reason")
    op.drop_column("deals", "cancelled_by_id")
    for column in reversed(_TS_COLUMNS):
        op.drop_column("deals", column)
    op.execute("DROP TYPE deal_cancel_reason")
