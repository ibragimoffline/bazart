"""Telefon OTP: E.164 raqamlar, bitta tasdiqlangan raqam = bitta akkaunt, kod akkauntga bog'liq

1. `users.phone` +998XXXXXXXXX ko'rinishiga keltiriladi. Keltirib bo'lmaydigan raqam
   saqlanadi, lekin tasdig'i olinadi (qayta tasdiqlash kerak).
2. Bir xil raqam bir nechta faol akkauntda tasdiqlangan bo'lsa — eng birinchi tasdiqlangani
   qoladi, qolganlarining tasdig'i olinadi (raqam o'chirilmaydi).
3. `uq_users_verified_phone` — qisman UNIQUE indeks (tasdiqlangan, o'chirilmagan akkauntlar).
4. `otp_codes.user_id` — kod so'ragan akkaunt (eski kodlarda NULL; ular 5 daqiqada eskiradi).
5. `notification_type` ga `PHONE_CHANGED` (0035 naqshi: tur almashtiriladi).

Downgrade 1-2 bandni qaytarmaydi: keltirilgan raqam eski tekshiruvdan ham o'tadi, olingan
tasdiqni tiklash esa yana takroriy raqamlarni yaratardi.

Revision ID: 202610210038
Revises: 202610200037
Create Date: 2026-10-21 00:00:00.000000

"""

import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202610210038"
down_revision: str | None = "202610200037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFICATION_BEFORE = (
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
    "DEAL_MARKED_SOLD",
    "DEAL_COMPLETED",
    "DEAL_CANCELLED",
)
NOTIFICATION_ADDED = ("PHONE_CHANGED",)

_SEPARATORS = re.compile(r"[\s\-().]")


def _normalize(value: str) -> str | None:
    """app/schemas/user.normalize_phone nusxasi (migratsiya ilova kodiga bog'lanmasin)."""
    digits = _SEPARATORS.sub("", value.strip()).removeprefix("+")
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits.isdigit():
        return None
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) != 12 or not digits.startswith("998"):
        return None
    return "+" + digits


def _replace_notification_type(values: Sequence[str]) -> None:
    labels = ", ".join(f"'{v}'" for v in values)
    op.execute("ALTER TYPE notification_type RENAME TO notification_type_old")
    op.execute(f"CREATE TYPE notification_type AS ENUM ({labels})")
    op.execute(
        "ALTER TABLE notifications ALTER COLUMN type TYPE notification_type "
        "USING type::text::notification_type"
    )
    op.execute("DROP TYPE notification_type_old")


def upgrade() -> None:
    conn = op.get_bind()
    users = conn.execute(
        sa.text(
            "SELECT id, phone, phone_verified_at, deleted_at FROM users "
            "WHERE phone IS NOT NULL ORDER BY phone_verified_at NULLS LAST, id"
        )
    ).fetchall()
    claimed: set[str] = set()
    for user_id, phone, verified_at, deleted_at in users:
        normalized = _normalize(phone)
        keep_verified = verified_at is not None and normalized is not None
        if keep_verified and deleted_at is None:
            if normalized in claimed:
                keep_verified = False  # eng birinchi tasdiqlangan akkaunt raqamni saqlaydi
            else:
                claimed.add(normalized)
        conn.execute(
            sa.text(
                "UPDATE users SET phone = :phone, phone_verified_at = CASE WHEN :keep "
                "THEN phone_verified_at ELSE NULL END WHERE id = :id"
            ),
            {"phone": normalized or phone, "keep": keep_verified, "id": user_id},
        )

    op.create_index(
        "uq_users_verified_phone",
        "users",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("phone_verified_at IS NOT NULL AND deleted_at IS NULL"),
    )

    op.add_column("otp_codes", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "otp_codes_user_id_fkey", "otp_codes", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index(op.f("ix_otp_codes_user_id"), "otp_codes", ["user_id"], unique=False)

    _replace_notification_type(NOTIFICATION_BEFORE + NOTIFICATION_ADDED)


def downgrade() -> None:
    labels = ", ".join(f"'{v}'" for v in NOTIFICATION_ADDED)
    op.execute(f"DELETE FROM notifications WHERE type::text IN ({labels})")
    _replace_notification_type(NOTIFICATION_BEFORE)

    op.drop_index(op.f("ix_otp_codes_user_id"), table_name="otp_codes")
    op.drop_constraint("otp_codes_user_id_fkey", "otp_codes", type_="foreignkey")
    op.drop_column("otp_codes", "user_id")

    op.drop_index("uq_users_verified_phone", table_name="users")
