"""Faza E2.12: kelishuv bildirishnoma turlari

`notification_type` ga `DEAL_MARKED_SOLD`, `DEAL_COMPLETED`, `DEAL_CANCELLED`. Postgres enum
qiymatini o'chira olmaydi, shuning uchun (downgrade ham ishlashi uchun) tur yangisi bilan
almashtiriladi: yangi tur yaratiladi, ustun unga o'tkaziladi, eskisi o'chiriladi.
Downgrade yangi turdagi bildirishnomalarni o'chiradi.

Revision ID: 202610200035
Revises: 202610200034
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200035"
down_revision: str | None = "202610200034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = (
    "OUTBID",
    "WON",
    "SOLD",
    "SECOND_CHANCE",
    "ENDING_SOON",
    "OFFER_RECEIVED",
    "OFFER_COUNTERED",
    "OFFER_ACCEPTED",
    "OFFER_CLOSED",
    "DUTCH_STARTED",
    "PRICE_DROPPED",
)
ADDED = ("DEAL_MARKED_SOLD", "DEAL_COMPLETED", "DEAL_CANCELLED")


def _replace(values: Sequence[str]) -> None:
    labels = ", ".join(f"'{v}'" for v in values)
    op.execute("ALTER TYPE notification_type RENAME TO notification_type_old")
    op.execute(f"CREATE TYPE notification_type AS ENUM ({labels})")
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN type TYPE notification_type "
        "USING type::text::notification_type"
    )
    op.execute("DROP TYPE notification_type_old")


def upgrade() -> None:
    _replace(BEFORE + ADDED)


def downgrade() -> None:
    labels = ", ".join(f"'{v}'" for v in ADDED)
    op.execute(f"DELETE FROM notifications WHERE type::text IN ({labels})")
    _replace(BEFORE)
