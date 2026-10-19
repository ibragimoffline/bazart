"""Faza E2.2: orders -> deals (kelishuv)

`orders` jadvali `deals` ga qayta nomlanadi (ustunlar, indekslar, cheklovlar, ketma-ketlik),
`reviews.order_id` -> `reviews.deal_id`. Holat turi `order_status` o'rniga `deal_status`:
`AGREED`, `COMPLETED`, `CANCELLED`. Ochiq buyurtmalar (`PENDING_PAYMENT`, `PICKUP_PENDING`)
`AGREED` ga o'tadi. Shikoyat nishoni `ORDER` -> `DEAL`.

Downgrade nomlarni qaytaradi; `AGREED` -> `PENDING_PAYMENT` (oraliq holat tiklanmaydi).

Revision ID: 202610200030
Revises: 202610200029
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200030"
down_revision: str | None = "202610200029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (eski, yangi) — jadval ichidagi nomlar.
_DEAL_CONSTRAINTS = (
    ("orders_pkey", "deals_pkey"),
    ("orders_auction_id_key", "deals_auction_id_key"),
    ("orders_offer_id_key", "deals_offer_id_key"),
    ("orders_auction_id_fkey", "deals_auction_id_fkey"),
    ("orders_buyer_id_fkey", "deals_buyer_id_fkey"),
    ("orders_item_id_fkey", "deals_item_id_fkey"),
    ("orders_seller_id_fkey", "deals_seller_id_fkey"),
    ("fk_orders_offer_id_offers", "fk_deals_offer_id_offers"),
    ("ck_orders_final_price_positive", "ck_deals_final_price_positive"),
    ("ck_orders_single_source", "ck_deals_single_source"),
    ("ck_orders_quantity_positive", "ck_deals_quantity_positive"),
)
_DEAL_INDEXES = (
    ("ix_orders_buyer_id", "ix_deals_buyer_id"),
    ("ix_orders_id", "ix_deals_id"),
    ("ix_orders_item_id", "ix_deals_item_id"),
    ("ix_orders_seller_id", "ix_deals_seller_id"),
    ("ix_orders_status", "ix_deals_status"),
)
_REVIEW_CONSTRAINTS = (
    ("uq_reviews_order_from", "uq_reviews_deal_from"),
    ("reviews_order_id_fkey", "reviews_deal_id_fkey"),
)
_REVIEW_INDEXES = (("ix_reviews_order_id", "ix_reviews_deal_id"),)


def _rename(table: str, constraints, indexes, reverse: bool = False) -> None:
    for old, new in constraints:
        src, dst = (new, old) if reverse else (old, new)
        op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {src} TO {dst}")
    for old, new in indexes:
        src, dst = (new, old) if reverse else (old, new)
        op.execute(f"ALTER INDEX IF EXISTS {src} RENAME TO {dst}")


def _replace_enum(
    type_name: str, new_name: str, table: str, column: str, values, cast: str
) -> None:
    """Enum turini yangisi bilan almashtiradi; `cast` — eski matndan yangi qiymatga SQL ifoda."""
    op.execute(f"CREATE TYPE {new_name} AS ENUM ({', '.join(repr(v) for v in values)})")
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_name} USING ({cast})::{new_name}"
    )
    op.execute(f"DROP TYPE {type_name}")


def upgrade() -> None:
    op.rename_table("orders", "deals")
    op.execute("ALTER SEQUENCE orders_id_seq RENAME TO deals_id_seq")
    _rename("deals", _DEAL_CONSTRAINTS, _DEAL_INDEXES)
    _replace_enum(
        "order_status",
        "deal_status",
        "deals",
        "status",
        ("AGREED", "COMPLETED", "CANCELLED"),
        "CASE WHEN status::text IN ('PENDING_PAYMENT', 'PICKUP_PENDING') THEN 'AGREED' "
        "ELSE status::text END",
    )

    op.alter_column("reviews", "order_id", new_column_name="deal_id")
    _rename("reviews", _REVIEW_CONSTRAINTS, _REVIEW_INDEXES)

    _replace_enum(
        "complaint_target_type",
        "complaint_target_type_new",
        "complaints",
        "target_type",
        ("ITEM", "USER", "AUCTION", "MESSAGE", "DEAL"),
        "CASE WHEN target_type::text = 'ORDER' THEN 'DEAL' ELSE target_type::text END",
    )
    op.execute("ALTER TYPE complaint_target_type_new RENAME TO complaint_target_type")


def downgrade() -> None:
    _replace_enum(
        "complaint_target_type",
        "complaint_target_type_old",
        "complaints",
        "target_type",
        ("ITEM", "USER", "AUCTION", "MESSAGE", "ORDER"),
        "CASE WHEN target_type::text = 'DEAL' THEN 'ORDER' ELSE target_type::text END",
    )
    op.execute("ALTER TYPE complaint_target_type_old RENAME TO complaint_target_type")

    _rename("reviews", _REVIEW_CONSTRAINTS, _REVIEW_INDEXES, reverse=True)
    op.alter_column("reviews", "deal_id", new_column_name="order_id")

    _replace_enum(
        "deal_status",
        "order_status",
        "deals",
        "status",
        ("PENDING_PAYMENT", "PICKUP_PENDING", "COMPLETED", "CANCELLED"),
        "CASE WHEN status::text = 'AGREED' THEN 'PENDING_PAYMENT' ELSE status::text END",
    )
    _rename("deals", _DEAL_CONSTRAINTS, _DEAL_INDEXES, reverse=True)
    op.execute("ALTER SEQUENCE deals_id_seq RENAME TO orders_id_seq")
    op.rename_table("deals", "orders")
