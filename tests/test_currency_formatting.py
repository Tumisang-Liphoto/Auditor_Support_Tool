"""Audit-currency validation and human monetary formatting."""

from decimal import Decimal

import pytest

from auditor_support_tool.core.currency import (
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
