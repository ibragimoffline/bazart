"""Pul arifmetikasi. Pul HAR DOIM tiyinda (butun son).

Nega tiyin (butun son), Decimal/float emas:
- float bilan pul TAQIQ — 0.1 + 0.2 != 0.3, yaxlitlash xatolari yig'iladi.
- Decimal xavfsiz, lekin har amalda kontekst/aniqlik masalasi tug'iladi
  va JSON/DB chegaralarida jimgina float'ga aylanib ketishi mumkin.
- Butun son tiyin: bitta haqiqat, yaxlitlash faqat bitta joyda
  (calc_buyer_premium ichida), taqqoslash va yig'indi aniq.

1 so'm = 100 tiyin.
"""

from app.money.money import (
    BUYER_PREMIUM_BPS,
    TIYIN_PER_SOUM,
    Tiyin,
    calc_buyer_premium,
    calc_descending_price,
    calc_dutch_step,
    calc_line_total,
    calc_seller_payout,
    calc_total,
    dropped_by_at_least,
    format_soum,
    format_soum_text,
    soum_to_tiyin,
    tiyin_to_soum,
)

__all__ = [
    "BUYER_PREMIUM_BPS",
    "TIYIN_PER_SOUM",
    "Tiyin",
    "calc_buyer_premium",
    "calc_seller_payout",
    "calc_total",
    "calc_descending_price",
    "calc_dutch_step",
    "calc_line_total",
    "dropped_by_at_least",
    "format_soum",
    "format_soum_text",
    "soum_to_tiyin",
    "tiyin_to_soum",
]
