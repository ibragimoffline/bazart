"""Faza E2.10: keyingi bidderga taklif

- `deals.auction_id` UNIQUE -> qisman UNIQUE (`auction_id IS NOT NULL AND status <>
  'CANCELLED'`): g'olib javob bermay bekor qilingan kelishuvdan keyin keyingi bidder bilan
  yangi kelishuv tuziladi, lekin bir auksionda bir vaqtda faqat bitta tirik kelishuv
  (mahsulot ikki marta sotilmaydi). Shart "bekor qilinmagan" — E5 dagi fee_pending ham
  qamraladi, qo'shimcha migratsiya kerak emas.
- `next_bidder_offers`: har taklif yozuvi (kim, qaysi bid, narx, muddat, natija).
  UNIQUE (auction_id, bidder_id) — bidder bir auksionda bitta taklif oladi.

Downgrade: bitta auksionda bir nechta kelishuv bo'lsa UNIQUE tiklanmaydi (xato beradi) —
ma'lumot jimgina buzilmasin.

Revision ID: 202610200034
Revises: 202610200033
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200034"
down_revision: str | None = "202610200033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("deals_auction_id_key", "deals", type_="unique")
    op.create_index("ix_deals_auction_id", "deals", ["auction_id"])
    op.create_index(
        "uq_deals_auction_active",
        "deals",
        ["auction_id"],
        unique=True,
        postgresql_where=sa.text("auction_id IS NOT NULL AND status <> 'CANCELLED'"),
    )

    op.create_table(
        "next_bidder_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auction_id", sa.Integer(), sa.ForeignKey("auctions.id"), nullable=False),
        sa.Column("bidder_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bid_id", sa.Integer(), sa.ForeignKey("bids.id"), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id"), nullable=True),
        sa.UniqueConstraint("auction_id", "bidder_id", name="uq_next_bidder_offers_auction_bidder"),
    )
    op.create_index("ix_next_bidder_offers_id", "next_bidder_offers", ["id"])
    op.create_index("ix_next_bidder_offers_auction_id", "next_bidder_offers", ["auction_id"])


def downgrade() -> None:
    op.drop_index("ix_next_bidder_offers_auction_id", table_name="next_bidder_offers")
    op.drop_index("ix_next_bidder_offers_id", table_name="next_bidder_offers")
    op.drop_table("next_bidder_offers")
    op.drop_index("uq_deals_auction_active", table_name="deals")
    op.drop_index("ix_deals_auction_id", table_name="deals")
    op.create_unique_constraint("deals_auction_id_key", "deals", ["auction_id"])
