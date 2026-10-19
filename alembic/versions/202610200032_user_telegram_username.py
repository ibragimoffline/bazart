"""Faza E2.5: users.telegram_username (kelishuvda ochiladigan Telegram kontakti)

`telegram_chat_id` — bot uchun ichki identifikator, ikkinchi tomonga foydasiz va oshkor
qilinmaydi. Kontakt sifatida foydalanuvchi o'zi kiritgan @nom ochiladi.

Revision ID: 202610200032
Revises: 202610200031
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200032"
down_revision: str | None = "202610200031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("telegram_username", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "telegram_username")
