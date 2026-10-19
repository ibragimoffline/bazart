"""Tiyin arifmetikasi — pul bilan bog'liq yagona hisob-kitob joyi."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Pul turi. Bu shunchaki int alias'i — lekin tipda niyatni ko'rsatadi:
# "bu qiymat tiyinda, so'mda emas".
Tiyin = int

TIYIN_PER_SOUM = 100

# BPS = basis points: 10 000 BPS = 100%.
_BPS_DIVISOR = 10_000


def soum_to_tiyin(value: Decimal | int | str) -> Tiyin:
    """So'mni tiyinga o'giradi: 62_000.50 -> 6_200_050.

    float QABUL QILINMAYDI — float'da 62_000.50 aniq ifodalanmaydi va
    jimgina bir tiyin yo'qolishi mumkin. Decimal, int yoki string bering.

    :raises TypeError: float berilsa.
    :raises ValueError: qiymat noto'g'ri yoki tiyindan mayda bo'lsa.
    """
    if isinstance(value, float):
        raise TypeError("float bilan pul TAQIQ — aniqlik yo'qoladi. Decimal, int yoki str bering.")

    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Pul qiymati noto'g'ri: {value!r}") from exc

    tiyin = amount * TIYIN_PER_SOUM
    if tiyin != tiyin.to_integral_value():
        raise ValueError(
            f"{value!r} tiyindan mayda — pul birligi tiyin, undan kichigi mavjud emas."
        )
    return int(tiyin)


def calc_descending_price(
    starting_price: Tiyin, price_decrement: Tiyin, intervals: int, floor_price: Tiyin
) -> Tiyin:
    """Pasayuvchi auksion narxi: boshlang'ich - (o'tgan oraliqlar x qadam), pastki chegaradan
    past emas.

    Butun son ayirmasi — yaxlitlash yo'q. `intervals` — butun oraliqlar soni (vaqt
    hisobi `services/price_schedule.py` da). Narx hech qachon `floor_price` (rezerv)
    dan pastga tushmaydi va boshlang'ichdan oshmaydi.
    """
    if starting_price <= 0 or price_decrement <= 0 or floor_price <= 0:
        raise ValueError("Narx, qadam va pastki chegara musbat bo'lishi shart")
    if floor_price > starting_price:
        raise ValueError("Pastki chegara boshlang'ich narxdan yuqori bo'lishi mumkin emas")
    if intervals <= 0:
        return starting_price
    return max(floor_price, starting_price - intervals * price_decrement)


def calc_dutch_step(
    starting_price: Tiyin, floor_price: Tiyin, steps: int, unit: Tiyin = TIYIN_PER_SOUM
) -> Tiyin:
    """Pasayuvchi bosqich qadami: boshlang'ichdan chegaragacha `steps` qadamda yetish uchun.

    YUQORIGA yaxlitlanadi (`unit` ga, default 1 so'm): qadam kichik chiqsa narx
    belgilangan vaqtda chegaraga yetmay qolardi; katta chiqsa — biroz oldinroq yetadi
    va chegarada to'xtaydi (`calc_descending_price` pastga tushirmaydi). Kamida `unit`.
    """
    if steps <= 0 or unit <= 0:
        raise ValueError("Qadamlar soni va birlik musbat bo'lishi shart")
    if not 0 < floor_price < starting_price:
        raise ValueError("Chegara 0 dan katta va boshlang'ich narxdan past bo'lishi shart")
    raw = -(-(starting_price - floor_price) // steps)  # butun sonli ceil
    rounded = -(-raw // unit) * unit
    return max(unit, rounded)


def dropped_by_at_least(previous: Tiyin, current: Tiyin, min_bps: int) -> bool:
    """`current` `previous` dan kamida `min_bps` (1000 = 10%) past-mi.

    Butun son taqqoslash (bo'lish yo'q): current * 10000 <= previous * (10000 - bps).
    """
    if previous <= 0 or not 0 < min_bps < _BPS_DIVISOR:
        raise ValueError("Narx musbat, bps esa 0..10000 oralig'ida bo'lishi shart")
    return current * _BPS_DIVISOR <= previous * (_BPS_DIVISOR - min_bps)


def calc_line_total(unit_price: Tiyin, quantity: int) -> Tiyin:
    """Dona narxi x miqdor = jami (taklif / deal qatori).

    Narxlar har doim DONA uchun saqlanadi; jami faqat shu yerda hisoblanadi —
    butun son ko'paytmasi, yaxlitlash yo'q.
    """
    if unit_price < 0 or quantity < 1:
        raise ValueError("Dona narxi manfiy, miqdor esa 1 dan kichik bo'lishi mumkin emas")
    return unit_price * quantity


def tiyin_to_soum(value: Tiyin) -> Decimal:
    """Tiyinni so'mga o'giradi (ko'rsatish uchun): 6_200_050 -> Decimal('62000.50').

    Faqat KO'RSATISH uchun. Hisob-kitob tiyinda qilinadi.
    """
    _assert_tiyin(value)
    return (Decimal(value) / TIYIN_PER_SOUM).quantize(Decimal("0.01"))


def format_soum(value: Tiyin) -> str:
    """Foydalanuvchiga ko'rsatish uchun matn: 6_200_050 -> '62 000.50'."""
    soum = tiyin_to_soum(value)
    whole, _, fraction = f"{soum:.2f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", " ")
    return f"{grouped}.{fraction}"


def format_soum_text(value: Tiyin) -> str:
    """Xabar matni uchun: butun so'mda kasrsiz — 420_000_000 -> '4 200 000'; tiyin bo'lsa
    `format_soum` kabi '62 000.50' (yaxlitlanmaydi, faqat ".00" tashlanadi)."""
    text = format_soum(value)
    return text[:-3] if text.endswith(".00") else text


def _assert_tiyin(value: Tiyin) -> None:
    """Tiyin butun va manfiy emasligini tekshiradi.

    bool ham int — lekin pul emas, shuning uchun alohida rad etiladi.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Tiyin butun son bo'lishi kerak, berildi: {type(value).__name__}")
    if value < 0:
        raise ValueError(f"Pul manfiy bo'lishi mumkin emas: {value}")


def quantize_soum(value: Decimal) -> Decimal:
    """Decimal so'mni tiyingacha yaxlitlaydi (eski ma'lumot ko'chirishda kerak)."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
