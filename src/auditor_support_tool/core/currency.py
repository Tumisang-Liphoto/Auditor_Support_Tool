"""Audit-currency validation and monetary display helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

DEFAULT_CURRENCY_CODE = "LSL"

# Presentation symbols are deliberately explicit. Unknown valid currency codes
# fall back to the code itself rather than guessing a symbol.
_CURRENCY_SYMBOLS: dict[str, str] = {
    "LSL": "M",
    "ZAR": "R",
    "USD": "$",
    "GBP": "£",
    "EUR": "€",
    "BWP": "P",
    "KES": "KSh",
}

# Canonical audit fields/metrics that represent monetary values. This is an
# explicit semantic allow-list; callers must not infer money from arbitrary
# numeric values or field-name substrings.
MONETARY_FIELD_KEYS = frozenset(
    {
        "amount",
        "balance",
        "closing_balance",
        "credit_amount",
        "debit_amount",
        "gross_amount",
        "high_value_threshold",
        "materiality",
        "net_amount",
        "opening_balance",
        "payment_amount",
        "related_value",
        "related_value_total",
        "salary_amount",
        "saturday_credit_total",
        "saturday_debit_total",
        "sunday_credit_total",
        "sunday_debit_total",
        "transaction_amount",
        "transaction_amount_total",
        "weekend_credit_total",
        "weekend_debit_total",
    }
)


def normalise_currency_code(
    value: object,
    *,
    allow_blank: bool = False,
    default: str = DEFAULT_CURRENCY_CODE,
) -> str:
    """Return a validated upper-case three-letter audit currency code."""

    cleaned = str(value or "").strip().upper()

    if not cleaned:
        if allow_blank:
            return ""
        cleaned = str(default or DEFAULT_CURRENCY_CODE).strip().upper()

    if len(cleaned) != 3 or not cleaned.isascii() or not cleaned.isalpha():
        raise ValueError("Audit currency must be a three-letter code such as LSL or USD.")

    return cleaned


def is_monetary_field(field_key: object) -> bool:
    """Return whether a canonical field or metric has monetary semantics."""

    return str(field_key or "").strip().lower() in MONETARY_FIELD_KEYS


def format_monetary_value(
    value: object,
    currency_code: object,
) -> str:
    """Format one monetary value without changing its underlying stored value."""

    amount = _as_decimal(value)

    if amount is None:
        return "—" if value is None else str(value)

    code = normalise_currency_code(currency_code, allow_blank=True)
    absolute = abs(amount)
    number = f"{absolute:,.2f}"
    negative_prefix = "-" if amount < 0 else ""

    if not code:
        return f"{negative_prefix}{number}"

    symbol = _CURRENCY_SYMBOLS.get(code)

    if symbol is not None:
        return f"{negative_prefix}{symbol}{number}"

    return f"{negative_prefix}{code} {number}"


def _as_decimal(value: object) -> Decimal | None:
    """Interpret a supported numeric value as Decimal for display only."""

    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, Decimal):
        return value if value.is_finite() else None

    if isinstance(value, (int, float)):
        try:
            converted = Decimal(str(value))
        except InvalidOperation:
            return None
        return converted if converted.is_finite() else None

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if not cleaned:
            return None
        try:
            converted = Decimal(cleaned)
        except InvalidOperation:
            return None
        return converted if converted.is_finite() else None

    return None
