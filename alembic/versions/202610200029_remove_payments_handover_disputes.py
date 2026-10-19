"""Faza E1: to'lov, topshirish va nizo qatlamini olib tashlash

Bazart savdo to'lovida ishtirok etmaydi. O'chiriladi: `payments`, `payment_methods`,
`handovers`, `disputes` jadvallari va ularning enum'lari, `orders.auto_complete_at`.
`order_status` dan `PAID`, `notification_type` dan `PAYMENT`/`HANDOVER`/`DISPUTE` chiqariladi —
Postgres enum qiymatini o'chira olmaydi, shuning uchun tur yangisi bilan almashtiriladi.

Ma'lumot: `PAID` order'lar `PICKUP_PENDING` ga o'tadi (to'lov oqimi yo'q, sotuvchi yakunlaydi);
o'chirilgan turdagi bildirishnomalar o'chiriladi. Downgrade tuzilmani bo'sh holda qayta yaratadi
(to'lov, topshirish va nizo yozuvlari qaytmaydi).

Revision ID: 202610200029
Revises: 202610200028
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200029"
down_revision: str | None = "202610200028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_STATUS_NEW = ("PENDING_PAYMENT", "PICKUP_PENDING", "COMPLETED", "CANCELLED")
ORDER_STATUS_OLD = ("PENDING_PAYMENT", "PAID", "PICKUP_PENDING", "COMPLETED", "CANCELLED")
NOTIFICATION_REMOVED = ("PAYMENT", "HANDOVER", "DISPUTE")
NOTIFICATION_OLD = (
    "OUTBID",
    "WON",
    "SOLD",
    "PAYMENT",
    "HANDOVER",
    "DISPUTE",
    "SECOND_CHANCE",
    "ENDING_SOON",
    "OFFER_RECEIVED",
    "OFFER_COUNTERED",
    "OFFER_ACCEPTED",
    "OFFER_CLOSED",
    "DUTCH_STARTED",
    "PRICE_DROPPED",
)
NOTIFICATION_NEW = tuple(v for v in NOTIFICATION_OLD if v not in NOTIFICATION_REMOVED)


def _labels(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _replace_enum(type_name: str, table: str, column: str, values: Sequence[str]) -> None:
    """Enum turini berilgan qiymatlar bilan almashtiradi (ustun matn orqali o'tkaziladi)."""
    op.execute(f"ALTER TYPE {type_name} RENAME TO {type_name}_old")
    op.execute(f"CREATE TYPE {type_name} AS ENUM ({_labels(values)})")
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN {column} TYPE {type_name} "
        f"USING {column}::text::{type_name}"
    )
    op.execute(f"DROP TYPE {type_name}_old")


def upgrade() -> None:
    op.drop_table("disputes")
    op.drop_table("handovers")
    op.drop_table("payments")
    op.drop_table("payment_methods")
    for enum_name in (
        "dispute_reason",
        "dispute_status",
        "handover_method",
        "handover_status",
        "payment_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")

    op.drop_column("orders", "auto_complete_at")

    op.execute("UPDATE orders SET status = 'PICKUP_PENDING' WHERE status = 'PAID'")
    _replace_enum("order_status", "orders", "status", ORDER_STATUS_NEW)

    op.execute(f"DELETE FROM notifications WHERE type IN ({_labels(NOTIFICATION_REMOVED)})")
    _replace_enum("notification_type", "notifications", "type", NOTIFICATION_NEW)


def downgrade() -> None:
    _replace_enum("notification_type", "notifications", "type", NOTIFICATION_OLD)
    _replace_enum("order_status", "orders", "status", ORDER_STATUS_OLD)
    op.add_column(
        "orders", sa.Column("auto_complete_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.execute(
        "CREATE TYPE payment_status AS ENUM ('PENDING', 'PAID', 'FAILED', 'REFUNDED', "
        "'PROCESSING', 'HELD', 'RELEASED', 'CANCELLED_HOLD')"
    )
    op.execute("CREATE TYPE handover_method AS ENUM ('LOCAL_MEETUP', 'DELIVERY')")
    op.execute("CREATE TYPE handover_status AS ENUM ('PENDING', 'COMPLETED', 'FAILED')")
    op.execute(
        "CREATE TYPE dispute_reason AS ENUM "
        "('NOT_RECEIVED', 'NOT_AS_DESCRIBED', 'DAMAGED', 'FAKE', 'OTHER')"
    )
    op.execute(
        "CREATE TYPE dispute_status AS ENUM "
        "('OPEN', 'UNDER_REVIEW', 'RESOLVED_BUYER', 'RESOLVED_SELLER')"
    )

    op.execute(
        """
        CREATE TABLE payment_methods (
            id SERIAL PRIMARY KEY,
            user_id integer NOT NULL REFERENCES users(id),
            provider varchar(80) NOT NULL,
            label varchar(120),
            token_reference varchar(255),
            is_default boolean NOT NULL,
            created_at timestamp without time zone NOT NULL
        )
        """
    )
    op.create_index("ix_payment_methods_id", "payment_methods", ["id"])
    op.create_index("ix_payment_methods_user_id", "payment_methods", ["user_id"])

    op.execute(
        """
        CREATE TABLE payments (
            id SERIAL PRIMARY KEY,
            order_id integer NOT NULL REFERENCES orders(id),
            buyer_id integer NOT NULL REFERENCES users(id),
            amount bigint NOT NULL,
            currency varchar(3) NOT NULL,
            status payment_status NOT NULL,
            provider varchar(80) NOT NULL,
            provider_payment_id varchar(255),
            created_at timestamp without time zone NOT NULL,
            updated_at timestamp without time zone NOT NULL,
            premium bigint NOT NULL,
            total bigint NOT NULL,
            idempotency_key varchar(128),
            held_at timestamp with time zone,
            released_at timestamp with time zone,
            failed_reason varchar(255),
            CONSTRAINT ck_payments_amount_positive CHECK (amount > 0)
        )
        """
    )
    op.create_index("ix_payments_id", "payments", ["id"])
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_buyer_id", "payments", ["buyer_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.execute(
        "CREATE UNIQUE INDEX uq_payments_idempotency_key ON payments (idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )

    op.execute(
        """
        CREATE TABLE handovers (
            id SERIAL PRIMARY KEY,
            order_id integer NOT NULL REFERENCES orders(id),
            method handover_method NOT NULL,
            code varchar(16) NOT NULL,
            status handover_status NOT NULL,
            meet_address varchar(255),
            confirmed_at timestamp with time zone,
            created_at timestamp without time zone NOT NULL
        )
        """
    )
    op.create_index("ix_handovers_id", "handovers", ["id"])
    op.create_index("ix_handovers_order_id", "handovers", ["order_id"], unique=True)
    op.create_index("ix_handovers_status", "handovers", ["status"])

    op.execute(
        """
        CREATE TABLE disputes (
            id SERIAL PRIMARY KEY,
            order_id integer NOT NULL REFERENCES orders(id),
            payment_id integer NOT NULL REFERENCES payments(id),
            opened_by integer NOT NULL REFERENCES users(id),
            reason dispute_reason NOT NULL,
            description text,
            status dispute_status NOT NULL,
            resolution text,
            resolved_by integer REFERENCES users(id),
            resolved_at timestamp with time zone,
            created_at timestamp without time zone NOT NULL
        )
        """
    )
    op.create_index("ix_disputes_id", "disputes", ["id"])
    op.create_index("ix_disputes_order_id", "disputes", ["order_id"])
    op.create_index("ix_disputes_opened_by", "disputes", ["opened_by"])
    op.create_index("ix_disputes_status", "disputes", ["status"])
