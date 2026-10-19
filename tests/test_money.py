"""Pul arifmetikasi testlari.

Pul modulida xato = to'g'ridan-to'g'ri pul yo'qotish. Shu sababli bu yerda
chegaraviy holatlar (yaxlitlash, float, manfiy, juda katta summa) alohida
tekshiriladi.
"""

from decimal import Decimal

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.money import (
    format_soum,
    soum_to_tiyin,
    tiyin_to_soum,
)
from app.money.fields import TiyinAmount


class TestSoumToTiyin:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (Decimal("0"), 0),
            (Decimal("1"), 100),
            (Decimal("62000.50"), 6_200_050),
            (Decimal("0.01"), 1),
            (100, 10_000),
            ("62000.50", 6_200_050),
        ],
    )
    def test_converts_correctly(self, value: Decimal | int | str, expected: int) -> None:
        assert soum_to_tiyin(value) == expected

    def test_float_is_rejected(self) -> None:
        """float bilan pul TAQIQ — aniqlik jimgina yo'qoladi."""
        with pytest.raises(TypeError, match="float"):
            soum_to_tiyin(62000.50)

    def test_sub_tiyin_precision_is_rejected(self) -> None:
        """Tiyindan mayda qiymat jimgina yaxlitlanmaydi — xato beradi."""
        with pytest.raises(ValueError, match="mayda"):
            soum_to_tiyin(Decimal("0.001"))

    def test_garbage_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            soum_to_tiyin("salom")


class TestTiyinToSoum:
    def test_converts_back(self) -> None:
        assert tiyin_to_soum(6_200_050) == Decimal("62000.50")

    def test_round_trip_is_lossless(self) -> None:
        original = Decimal("123456.78")
        assert tiyin_to_soum(soum_to_tiyin(original)) == original

    def test_negative_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="manfiy"):
            tiyin_to_soum(-1)

    def test_bool_is_not_money(self) -> None:
        """bool ham int — lekin pul emas."""
        with pytest.raises(TypeError):
            tiyin_to_soum(True)


class TestLargeAmounts:
    def test_no_precision_loss_at_uzs_scale(self) -> None:
        """UZS summalari katta — Numeric(12,2) bunga tor edi (~10 mlrd so'm).

        Butun sonli tiyinda Python cheklovsiz — 1 trillion so'm ham aniq.
        """
        one_trillion_soum = soum_to_tiyin(Decimal("1000000000000"))
        assert one_trillion_soum == 100_000_000_000_000
        assert tiyin_to_soum(one_trillion_soum) == Decimal("1000000000000.00")

    def test_bigint_upper_bound_is_enough(self) -> None:
        """Postgres BIGINT chegarasi ~9.2 * 10^18 tiyin = ~92 kvadrillion so'm."""
        bigint_max = 2**63 - 1
        assert soum_to_tiyin(Decimal("92000000000000000")) < bigint_max


class _PriceModel(BaseModel):
    price: TiyinAmount = Field(gt=0)


class TestTiyinField:
    """API chegarasidagi pul turi.

    Regressiya himoyasi: dastlab bu tur `plain` validator bilan yozilgan
    edi va Field(gt=0) JIMGINA e'tiborsiz qolardi — manfiy va nol narx
    o'tib ketardi. `before` validator + int sxemasiga o'tildi.
    """

    def test_accepts_string_tiyin(self) -> None:
        assert _PriceModel(price="6200050").price == 6_200_050

    def test_accepts_int_tiyin(self) -> None:
        assert _PriceModel(price=6_200_050).price == 6_200_050

    def test_serializes_to_string_in_json(self) -> None:
        """JS `number` katta butun sonni buzadi — shuning uchun string."""
        assert _PriceModel(price=6_200_050).model_dump_json() == '{"price":"6200050"}'

    def test_json_schema_reports_integer(self) -> None:
        schema = _PriceModel.model_json_schema()["properties"]["price"]
        assert schema["type"] == "integer"
        assert schema["exclusiveMinimum"] == 0

    @pytest.mark.parametrize(
        ("value", "reason"),
        [
            (-5, "manfiy"),
            (0, "nol (gt=0)"),
            (62000.50, "float"),
            (True, "bool"),
            ("salom", "matn"),
            ("62000.50", "kasrli string — tiyin butun bo'lishi kerak"),
            ("", "bo'sh"),
        ],
    )
    def test_rejects_invalid(self, value: object, reason: str) -> None:
        with pytest.raises(ValidationError):
            _PriceModel(price=value)


class TestFormatSoum:
    @pytest.mark.parametrize(
        ("tiyin", "expected"),
        [
            (6_200_050, "62 000.50"),
            (100, "1.00"),
            (0, "0.00"),
            (100_000_000, "1 000 000.00"),
        ],
    )
    def test_formats_for_display(self, tiyin: int, expected: str) -> None:
        assert format_soum(tiyin) == expected
