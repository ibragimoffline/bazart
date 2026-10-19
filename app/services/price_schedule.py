"""Pasayuvchi (golland) auksion narx jadvali — vaqtdan hisoblanadi, bazada saqlanmaydi.

Narx hech qachon fon vazifasi bilan "tushirilmaydi": har o'qishda va har xaridda
o'tgan vaqtdan qayta hisoblanadi. Shu sabab Celery kechiksa yoki to'xtasa ham narx
aniq qoladi, va xarid paytida qulf ostida hisoblangan narx — yagona haqiqat.

Bu modul faqat VAQTNI hisoblaydi (butun oraliqlar soni); pul arifmetikasi —
`app/money.calc_descending_price` da.
"""

from datetime import UTC, datetime, timedelta

from app.money import Tiyin, calc_descending_price


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def elapsed_intervals(start_time: datetime, at: datetime, interval_minutes: int) -> int:
    """`start_time` dan `at` gacha to'liq o'tgan oraliqlar soni (boshlanmagan bo'lsa 0)."""
    if interval_minutes <= 0:
        raise ValueError("Oraliq musbat bo'lishi shart")
    elapsed = (_as_utc(at) - _as_utc(start_time)).total_seconds()
    if elapsed <= 0:
        return 0
    return int(elapsed // (interval_minutes * 60))


def descending_price_at(
    *,
    starting_price: Tiyin,
    price_decrement: Tiyin,
    interval_minutes: int,
    floor_price: Tiyin,
    start_time: datetime,
    at: datetime,
) -> Tiyin:
    """`at` paytidagi narx (tiyin)."""
    intervals = elapsed_intervals(start_time, at, interval_minutes)
    return calc_descending_price(starting_price, price_decrement, intervals, floor_price)


def next_price_drop_at(
    *,
    starting_price: Tiyin,
    price_decrement: Tiyin,
    interval_minutes: int,
    floor_price: Tiyin,
    start_time: datetime,
    at: datetime,
) -> datetime | None:
    """Keyingi pasayish vaqti; narx pastki chegaraga yetgan bo'lsa None."""
    intervals = elapsed_intervals(start_time, at, interval_minutes)
    current = calc_descending_price(starting_price, price_decrement, intervals, floor_price)
    if current <= floor_price:
        return None
    return _as_utc(start_time) + timedelta(minutes=interval_minutes * (intervals + 1))
