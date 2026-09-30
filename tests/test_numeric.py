"""Tests for strict shared audit numeric parsing."""

from decimal import Decimal

import pytest

from auditor_support_tool.core.numeric import (
    NonFiniteNumericError,
    NonIntegralNumericError,
    NumericParseError,
    parse_finite_decimal,
    parse_whole_number,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("1,250", Decimal("1250")),
        ("100,000.00", Decimal("100000.00")),
        ("-1,234.50", Decimal("-1234.50")),
        ("1250.50", Decimal("1250.50")),
        (".5", Decimal("0.5")),
        ("1E3", Decimal("1E3")),
        (1250, Decimal("1250")),
        (1250.5, Decimal("1250.5")),
        (Decimal("0"), Decimal("0")),
    ),
)
def test_parse_finite_decimal_accepts_unambiguous_values(
    value,
    expected: Decimal,
) -> None:
    assert parse_finite_decimal(value) == expected


@pytest.mark.parametrize(
    "value",
    (
        "1,25",
        "12,34,567",
        "1,234,56",
        "1,,234",
        "1,234e2",
    ),
)
def test_parse_finite_decimal_rejects_ambiguous_or_invalid_grouping(value: str) -> None:
    with pytest.raises(NumericParseError, match="comma grouping"):
        parse_finite_decimal(value)


@pytest.mark.parametrize(
    "value",
    (
        Decimal("NaN"),
        Decimal("Infinity"),
        float("inf"),
        float("-inf"),
        "NaN",
        "Infinity",
        "-Infinity",
    ),
)
def test_parse_finite_decimal_rejects_non_finite_values(value) -> None:
    with pytest.raises(NonFiniteNumericError):
        parse_finite_decimal(value)


def test_parse_finite_decimal_rejects_boolean() -> None:
    with pytest.raises(NumericParseError, match="Boolean"):
        parse_finite_decimal(True)


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("1,250", 1250),
        (1250, 1250),
        (1250.0, 1250),
        (Decimal("1250.000"), 1250),
        ("1E3", 1000),
    ),
)
def test_parse_whole_number_accepts_exact_whole_numbers(value, expected: int) -> None:
    assert parse_whole_number(value) == expected


@pytest.mark.parametrize(
    "value",
    (
        "1250.5",
        1250.5,
        Decimal("1250.5"),
    ),
)
def test_parse_whole_number_rejects_fractional_values(value) -> None:
    with pytest.raises(NonIntegralNumericError):
        parse_whole_number(value)
