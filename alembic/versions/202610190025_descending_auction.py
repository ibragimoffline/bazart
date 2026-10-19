"""pasayuvchi (golland) auksion: auctions.pricing_mode, price_decrement, price_drop_interval

Revision ID: 202610190025
Revises: 202610190024
Create Date: 2026-10-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610190025"
down_revision: str | None = "202610190024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Postgres ENUM qiymatlari — Python enum NOMLARI (loyihadagi boshqa enumlar kabi).
PRICING_MODE = postgresql.ENUM("ASCENDING", "DESCENDING", name="pricing_mode", create_type=False)


def upgrade() -> None:
    PRICING_MODE.create(op.get_bind(), checkfirst=True)
    # Mavjud auksionlar — o'suvchi (server_default). Narx qiymatlariga tegilmaydi.
    op.add_column(
        "auctions",
        sa.Column("pricing_mode", PRICING_MODE, nullable=False, server_default="ASCENDING"),
    )
    op.add_column("auctions", sa.Column("price_decrement", sa.BigInteger(), nullable=True))
    op.add_column("auctions", sa.Column("price_drop_interval_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_auctions_descending_config",
        "auctions",
        "pricing_mode = 'ASCENDING' OR (price_decrement > 0 "
        "AND price_drop_interval_minutes > 0 AND reserve_price IS NOT NULL)",
    )


def downgrade() -> None:
    # Pasayuvchi auksionlar o'suvchi sifatida "tirilib" qolmasin: faollari bekor qilinadi.
    bind = op.get_bind()
    active = bind.execute(
        sa.text(
            "SELECT count(*) FROM auctions "
            "WHERE pricing_mode = 'DESCENDING' AND status IN ('ACTIVE', 'SCHEDULED')"
        )
    ).scalar_one()
    if active:
        raise RuntimeError(
            f"{active} ta faol pasayuvchi auksion bor — downgrade ularni o'suvchi auksionga "
            "aylantirib, narxni boshlang'ichga qaytaradi. Avval ularni yakunlang yoki bekor qiling."
        )
    op.drop_constraint("ck_auctions_descending_config", "auctions", type_="check")
    op.drop_column("auctions", "price_drop_interval_minutes")
    op.drop_column("auctions", "price_decrement")
    op.drop_column("auctions", "pricing_mode")
    PRICING_MODE.drop(op.get_bind(), checkfirst=True)
