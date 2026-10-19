"""taklifli savdo: items.listing_type/quantity/listing_ends_at, offers, offer_events, orders

Revision ID: 202610190024
Revises: 202610180023
Create Date: 2026-10-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610190024"
down_revision: str | None = "202610180023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Postgres ENUM qiymatlari — Python enum NOMLARI (loyihadagi boshqa enumlar kabi).
LISTING_TYPE = postgresql.ENUM("OFFER", "AUCTION", name="listing_type", create_type=False)
OFFER_STATUS = postgresql.ENUM(
    "PENDING",
    "ACCEPTED",
    "REJECTED",
    "WITHDRAWN",
    "EXPIRED",
    name="offer_status",
    create_type=False,
)
OFFER_PARTY = postgresql.ENUM("BUYER", "SELLER", name="offer_party", create_type=False)


def upgrade() -> None:
    # Mavjud enumlarga yangi qiymatlar (bu migratsiyada ISHLATILMAYDI — tranzaksiyada xavfsiz).
    op.execute("ALTER TYPE item_status ADD VALUE IF NOT EXISTS 'EXPIRED'")
    for value in ("OFFER_RECEIVED", "OFFER_COUNTERED", "OFFER_ACCEPTED", "OFFER_CLOSED"):
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")

    bind = op.get_bind()
    for enum in (LISTING_TYPE, OFFER_STATUS, OFFER_PARTY):
        enum.create(bind, checkfirst=True)

    # --- items: sotish rejimi, zaxira, e'lon muddati ---------------------------
    op.add_column("items", sa.Column("listing_type", LISTING_TYPE, nullable=True))
    op.add_column(
        "items", sa.Column("quantity_total", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "items", sa.Column("quantity_available", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column("items", sa.Column("listing_duration_days", sa.SmallInteger(), nullable=True))
    op.add_column("items", sa.Column("listing_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_items_listing_type"), "items", ["listing_type"])
    op.create_index(op.f("ix_items_listing_ends_at"), "items", ["listing_ends_at"])
    # Mavjud auksionli e'lonlar — AUCTION (qolganlari qoralama: NULL).
    op.execute(
        "UPDATE items SET listing_type = 'AUCTION' WHERE id IN (SELECT item_id FROM auctions)"
    )
    op.create_check_constraint(
        "ck_items_quantity_available_range",
        "items",
        "quantity_available >= 0 AND quantity_available <= quantity_total",
    )
    op.create_check_constraint("ck_items_quantity_total_positive", "items", "quantity_total >= 1")

    # --- offers + offer_events ---------------------------------------------------
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.BigInteger(), nullable=False),
        sa.Column("status", OFFER_STATUS, nullable=False),
        sa.Column("awaiting", OFFER_PARTY, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 1", name="ck_offers_quantity_positive"),
        sa.CheckConstraint("unit_price > 0", name="ck_offers_unit_price_positive"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offers_id"), "offers", ["id"])
    op.create_index(op.f("ix_offers_item_id"), "offers", ["item_id"])
    op.create_index(op.f("ix_offers_buyer_id"), "offers", ["buyer_id"])
    op.create_index(op.f("ix_offers_seller_id"), "offers", ["seller_id"])
    op.create_index(op.f("ix_offers_status"), "offers", ["status"])
    op.create_index(
        "uq_offers_open_per_buyer",
        "offers",
        ["item_id", "buyer_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    op.create_table(
        "offer_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("actor", OFFER_PARTY, nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("unit_price", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_offer_events_id"), "offer_events", ["id"])
    op.create_index(op.f("ix_offer_events_offer_id"), "offer_events", ["offer_id"])

    # --- orders: manba auksion YOKI taklif; miqdor va dona narxi -----------------
    op.alter_column("orders", "auction_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("orders", sa.Column("offer_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_orders_offer_id_offers", "orders", "offers", ["offer_id"], ["id"])
    op.create_unique_constraint("orders_offer_id_key", "orders", ["offer_id"])
    op.add_column("orders", sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))
    # Mavjud (auksion) order'lar: 1 dona, dona narxi = yakuniy narx. Pul qiymati
    # o'zgarmaydi — faqat nusxa (BIGINT -> BIGINT, tiyin).
    op.add_column("orders", sa.Column("unit_price", sa.BigInteger(), nullable=True))
    op.execute("UPDATE orders SET unit_price = final_price")
    op.alter_column("orders", "unit_price", existing_type=sa.BigInteger(), nullable=False)
    op.create_check_constraint(
        "ck_orders_single_source", "orders", "(auction_id IS NULL) <> (offer_id IS NULL)"
    )
    op.create_check_constraint("ck_orders_quantity_positive", "orders", "quantity >= 1")


def downgrade() -> None:
    # Taklif order'lari auction_id'siz — ular bilan pul yozuvlari (to'lov, nizo, sharh)
    # bog'liq. Jimgina o'chirish o'rniga downgrade TO'XTATILADI.
    bind = op.get_bind()
    offer_orders = bind.execute(
        sa.text("SELECT count(*) FROM orders WHERE offer_id IS NOT NULL")
    ).scalar_one()
    if offer_orders:
        raise RuntimeError(
            f"{offer_orders} ta taklif order'i bor — downgrade pul yozuvlarini yo'qotadi. "
            "Avval ularni qo'lda ko'chiring yoki arxivlang."
        )
    op.drop_constraint("ck_orders_quantity_positive", "orders", type_="check")
    op.drop_constraint("ck_orders_single_source", "orders", type_="check")
    op.drop_column("orders", "unit_price")
    op.drop_column("orders", "quantity")
    op.drop_constraint("orders_offer_id_key", "orders", type_="unique")
    op.drop_constraint("fk_orders_offer_id_offers", "orders", type_="foreignkey")
    op.drop_column("orders", "offer_id")
    op.alter_column("orders", "auction_id", existing_type=sa.Integer(), nullable=False)

    op.drop_index(op.f("ix_offer_events_offer_id"), table_name="offer_events")
    op.drop_index(op.f("ix_offer_events_id"), table_name="offer_events")
    op.drop_table("offer_events")
    op.drop_index("uq_offers_open_per_buyer", table_name="offers")
    for name in ("status", "seller_id", "buyer_id", "item_id", "id"):
        op.drop_index(op.f(f"ix_offers_{name}"), table_name="offers")
    op.drop_table("offers")

    op.drop_constraint("ck_items_quantity_total_positive", "items", type_="check")
    op.drop_constraint("ck_items_quantity_available_range", "items", type_="check")
    op.drop_index(op.f("ix_items_listing_ends_at"), table_name="items")
    op.drop_index(op.f("ix_items_listing_type"), table_name="items")
    # EXPIRED holatidagi e'lonlar eski enum'da yo'q qiymat bo'lib qoladi — CANCELLED'ga.
    op.execute("UPDATE items SET status = 'CANCELLED' WHERE status = 'EXPIRED'")
    op.drop_column("items", "listing_ends_at")
    op.drop_column("items", "listing_duration_days")
    op.drop_column("items", "quantity_available")
    op.drop_column("items", "quantity_total")
    op.drop_column("items", "listing_type")

    for enum in (OFFER_PARTY, OFFER_STATUS, LISTING_TYPE):
        enum.drop(bind, checkfirst=True)
    # Postgres enum qiymatini olib tashlab bo'lmaydi: item_status.EXPIRED va yangi
    # notification_type qiymatlari qoladi (ishlatilmaydi, zararsiz).
