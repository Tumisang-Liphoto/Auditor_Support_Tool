"""Strict numeric parsing helpers for audit data and procedure parameters."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_GROUPED_NUMBER_PATTERN = re.compile(
    r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$"
)


class NumericParseError(ValueError):
    """Raised when a value cannot be interpreted safely as a number."""


class NonFiniteNumericError(NumericParseError):
    """Raised when a numeric value is NaN or infinite."""


class NonIntegralNumericError(NumericParseError):
    """Raised when a value cannot be represented exactly as an integer."""


def parse_finite_decimal(value: object) -> Decimal:
    """Return a finite Decimal without guessing ambiguous comma semantics.

    Text containing commas is accepted only when the commas form conventional
    three-digit thousands groups, for example ``1,250`` or ``100,000.25``.
    Ambiguous forms such as ``1,25`` are rejected rather than interpreted as
    either a decimal-comma value or a thousands-grouped value.
    """

    if isinstance(value, bool):
        raise NumericParseError("Boolean values cannot be interpreted as numbers.")

    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, int):
        decimal_value = Decimal(value)
    elif isinstance(value, float):
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation as error:
            raise NumericParseError("The value is not a valid number.") from error
    elif isinstance(value, str):
        cleaned = value.strip()

        if not cleaned:
            raise NumericParseError("The numeric value is blank.")

        if "," in cleaned:
            if _GROUPED_NUMBER_PATTERN.fullmatch(cleaned) is None:
                raise NumericParseError(
                    "The numeric value uses invalid or ambiguous comma grouping."
                )
            cleaned = cleaned.replace(",", "")

        try:
            decimal_value = Decimal(cleaned)
        except InvalidOperation as error:
            raise NumericParseError("The value is not a valid number.") from error
    else:
        raise NumericParseError("The value cannot be interpreted as a number.")

    if not decimal_value.is_finite():
        raise NonFiniteNumericError("Non-finite numeric values are not supported.")

    return decimal_value


def parse_whole_number(value: object) -> int:
    """Return an exact integer using the shared audit numeric contract."""

    decimal_value = parse_finite_decimal(value)

    if decimal_value != decimal_value.to_integral_value():
        raise NonIntegralNumericError("The value is not a whole number.")

    return int(decimal_value)
