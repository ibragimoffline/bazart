"""telefon narx ko'rsatkichini olib tashlash (loyiha rejasida yo'q)

items.device_* ustunlari, device_models / device_prices / price_guide_settings jadvallari
va device_grade enum o'chiriladi. Downgrade tuzilmani bo'sh holda qayta yaratadi
(o'chirilgan narx ma'lumotlari va e'lonlardagi telefon maydonlari qaytmaydi).

Revision ID: 202610200028
Revises: 202610190027
Create Date: 2026-10-20 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610200028"
down_revision: str | None = "202610190027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEDUCTIONS = (
    "screen_broken",
    "lcd",
    "lcd_uninspectable",
    "face_id",
    "camera",
    "wifi",
    "mic",
    "back_glass",
    "true_tone",
    "genuine_parts",
    "nongenuine_parts",
    "scrap",
)


def upgrade() -> None:
    op.drop_column("items", "device_defects")
    op.drop_column("items", "battery_health")
    op.drop_column("items", "device_grade")
    op.drop_column("items", "device_storage")
    op.drop_index(op.f("ix_items_device_model_id"), table_name="items")
    op.drop_constraint("fk_items_device_model_id_device_models", "items", type_="foreignkey")
    op.drop_column("items", "device_model_id")
    sa.Enum(name="device_grade").drop(op.get_bind(), checkfirst=True)

    op.drop_table("price_guide_settings")
    op.drop_index(op.f("ix_device_prices_model_id"), table_name="device_prices")
    op.drop_index(op.f("ix_device_prices_id"), table_name="device_prices")
    op.drop_table("device_prices")
    op.drop_index(op.f("ix_device_models_slug"), table_name="device_models")
    op.drop_index(op.f("ix_device_models_id"), table_name="device_models")
    op.drop_table("device_models")


def downgrade() -> None:
    # 202610180023 dagi tuzilma (bo'sh) — ma'lumot tiklanmaydi.
    op.create_table(
        "device_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("brand", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("series", sa.String(length=20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *[sa.Column(f"{name}_krw", sa.BigInteger(), nullable=True) for name in DEDUCTIONS],
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_models_id"), "device_models", ["id"])
    op.create_index(op.f("ix_device_models_slug"), "device_models", ["slug"], unique=True)

    op.create_table(
        "device_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("storage", sa.String(length=10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *[
            sa.Column(f"{col}_krw", sa.BigInteger(), nullable=True)
            for col in (
                "grade_a",
                "grade_a_minus",
                "grade_b_plus",
                "grade_b_minus",
                "battery_low_a",
                "battery_low_b_plus",
                "base",
            )
        ],
        sa.ForeignKeyConstraint(["model_id"], ["device_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id", "storage", name="uq_device_prices_model_storage"),
    )
    op.create_index(op.f("ix_device_prices_id"), "device_prices", ["id"])
    op.create_index(op.f("ix_device_prices_model_id"), "device_prices", ["model_id"])

    op.create_table(
        "price_guide_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rate_tiyin_per_krw", sa.Integer(), nullable=False),
        sa.Column("market_adjust_bps", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    device_grade = postgresql.ENUM(
        "A", "A_MINUS", "B_PLUS", "B_MINUS", name="device_grade", create_type=False
    )
    device_grade.create(op.get_bind(), checkfirst=True)
    op.add_column("items", sa.Column("device_model_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_items_device_model_id_device_models",
        "items",
        "device_models",
        ["device_model_id"],
        ["id"],
    )
    op.create_index(op.f("ix_items_device_model_id"), "items", ["device_model_id"])
    op.add_column("items", sa.Column("device_storage", sa.String(length=10), nullable=True))
    op.add_column("items", sa.Column("device_grade", device_grade, nullable=True))
    op.add_column("items", sa.Column("battery_health", sa.SmallInteger(), nullable=True))
    op.add_column(
        "items",
        sa.Column("device_defects", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
