"""Audit-currency validation and human monetary formatting."""

from decimal import Decimal

import pytest

from auditor_support_tool.core.currency import (
    AUDIT_CURRENCY_ROLE,
    FX_CONVERSION_APPLIED,
    SOURCE_AMOUNT_CURRENCY_STATUS,
    format_monetary_value,
    is_monetary_field,
    normalise_currency_code,
)


def test_lsl_uses_maloti_symbol_and_two_decimals() -> None:
    assert format_monetary_value(Decimal("0"), "LSL") == "M0.00"
    assert format_monetary_value(Decimal("16000"), "LSL") == "M16,000.00"
    assert format_monetary_value(Decimal("-7000"), "LSL") == "-M7,000.00"


def test_known_and_unknown_currency_display_is_explicit() -> None:
    assert format_monetary_value(Decimal("1234.5"), "ZAR") == "R1,234.50"
    assert format_monetary_value(Decimal("1234.5"), "USD") == "$1,234.50"
    assert format_monetary_value(Decimal("1234.5"), "JPY") == "JPY 1,234.50"


def test_currency_code_validation_and_monetary_semantics_are_explicit() -> None:
    assert normalise_currency_code(" lsl ") == "LSL"
    assert normalise_currency_code("", allow_blank=True) == ""
    assert is_monetary_field("transaction_amount")
    assert not is_monetary_field("exception_count")

    with pytest.raises(ValueError, match="three-letter"):
        normalise_currency_code("Maloti")


def test_grouped_numeric_text_uses_shared_numeric_contract() -> None:
    assert format_monetary_value("1,250.50", "LSL") == "M1,250.50"


@pytest.mark.parametrize(
    "value",
    (
        "1,25",
        "12,34,567",
        "1,234,56",
    ),
)
def test_ambiguous_numeric_text_is_not_reinterpreted_for_display(value: str) -> None:
    """Presentation must not silently change ambiguous source values."""

    assert format_monetary_value(value, "LSL") == value


def test_currency_basis_policy_is_explicit() -> None:
    """Display currency must not be mistaken for verified source denomination."""

    assert AUDIT_CURRENCY_ROLE == "presentation_only"
    assert SOURCE_AMOUNT_CURRENCY_STATUS == "not_verified"
    assert FX_CONVERSION_APPLIED is False
