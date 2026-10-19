"""PSP webhook imzo utillari uchun sof unit testlar (DB kerak emas)."""

from app.core.webhook import compute_signature, is_fresh, verify_signature

_SECRET = "psp_super_secret"
_BODY = b'{"event":"payment.captured","deal_id":"42","amount":"6200050"}'


def test_verify_signature_valid() -> None:
    signature = compute_signature(_BODY, _SECRET)
    assert verify_signature(_BODY, signature, _SECRET) is True


def test_verify_signature_tampered_body() -> None:
    signature = compute_signature(_BODY, _SECRET)
    # Bir bayt o'zgargan body — imzo endi mos kelmasligi shart.
    tampered = _BODY.replace(b'"6200050"', b'"6200051"')
    assert tampered != _BODY
    assert verify_signature(tampered, signature, _SECRET) is False


def test_verify_signature_wrong_secret() -> None:
    signature = compute_signature(_BODY, _SECRET)
    assert verify_signature(_BODY, signature, "boshqa_secret") is False


def test_verify_signature_empty_signature() -> None:
    assert verify_signature(_BODY, "", _SECRET) is False


def test_verify_signature_malformed_signature_no_exception() -> None:
    # Hex bo'lmagan / uzunligi noto'g'ri imzo — istisno tashlamay, False qaytarishi kerak.
    assert verify_signature(_BODY, "not-a-hex-signature-zzz", _SECRET) is False
    assert verify_signature(_BODY, "deadbeef", _SECRET) is False


def test_compute_signature_deterministic() -> None:
    # Bir xil kirish → har doim bir xil chiqish.
    first = compute_signature(_BODY, _SECRET)
    second = compute_signature(_BODY, _SECRET)
    assert first == second
    # SHA256 hexdigest — 64 ta hex belgi.
    assert len(first) == 64


def test_compute_signature_changes_with_input() -> None:
    assert compute_signature(_BODY, _SECRET) != compute_signature(_BODY + b" ", _SECRET)
    assert compute_signature(_BODY, _SECRET) != compute_signature(_BODY, _SECRET + "x")


def test_is_fresh_recent_event() -> None:
    now = 1_700_000_000
    assert is_fresh(now - 10, now) is True


def test_is_fresh_old_event() -> None:
    now = 1_700_000_000
    # 600 soniya eski — standart 300 soniya chegarasidan oshadi.
    assert is_fresh(now - 600, now) is False


def test_is_fresh_boundary() -> None:
    now = 1_700_000_000
    # Aynan chegara (300 soniya) — hali yangi hisoblanadi.
    assert is_fresh(now - 300, now) is True
    # Chegaradan bir soniya oshsa — eski.
    assert is_fresh(now - 301, now) is False


def test_is_fresh_future_timestamp_allowed() -> None:
    now = 1_700_000_000
    # Kelajakdagi timestamp (soat farqi) — bloklanmaydi.
    assert is_fresh(now + 60, now) is True
