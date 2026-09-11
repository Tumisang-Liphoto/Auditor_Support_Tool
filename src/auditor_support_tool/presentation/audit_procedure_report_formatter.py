"""Generic formatting helpers for human-readable audit procedure reports."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ReportExceptionColumn:
    """One generic column shown in an audit report exception table."""

    key: str
    label: str


def report_display_label(key: str) -> str:
    """Convert a stable machine key into a readable report label."""

    cleaned = key.strip().replace("-", "_")

    if not cleaned:
        return ""

    special_labels = {
        "flagged_records": "Exceptions",
        "high_risk": "Matches Additional Indicators",
        "high_risk_available": "Additional Indicator Analysis Available",
        "high_risk_weekend_count": "Weekend Exceptions with Additional Indicators",
        "risk_indicators": "Additional Indicators",
        "evaluated_risk_indicators": "Evaluated Additional Indicators",
        "unavailable_risk_indicators": "Unavailable Additional Indicators",
        "distinct_conflicting_users": "Distinct Identifiers in Exceptions",
        "highest_self_approval_count": "Most Exceptions per Identifier",
        "user_self_approval_analysis": "Exceptions by User Identifier",
        "self_approvals": "Exceptions",
        "same_user_exceptions": "Matching User Identifier Exceptions",
        "same_preparer_approver_count": "Matching Preparer/Approver Identifier Count",
        "id": "ID",
        "sha256": "SHA-256",
        "source_sha256": "Source SHA-256",
        "mapping_fingerprint": "Mapping Fingerprint",
        "report_fingerprint": "Report Fingerprint",
    }

    if cleaned.lower() in special_labels:
        return special_labels[cleaned.lower()]

    words = cleaned.replace("_", " ").split()

    return " ".join(
        word.upper() if word.lower() in {"id", "url", "api"} else word.capitalize()
        for word in words
    )


def report_display_value(value: object) -> str:
    """Return a concise human-readable representation of a report value."""

    if value is None:
        return "—"

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, float):
        return f"{value:,.2f}"

    if isinstance(value, int):
        return f"{value:,}"

    if isinstance(value, datetime):
        return value.strftime("%d %b %Y, %H:%M")

    if isinstance(value, date):
        return value.strftime("%d %b %Y")

    if isinstance(value, str):
        return value if value.strip() else "—"

    if isinstance(value, Mapping):
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return ", ".join(report_display_value(item) for item in value)

    return str(value)


def build_exception_columns(
    exceptions: Sequence[object],
) -> tuple[ReportExceptionColumn, ...]:
    """Return deterministic columns for complete source-linked exceptions."""

    value_keys: list[str] = []
    seen: set[str] = set()

    for exception in exceptions:
        values = getattr(
            exception,
            "values",
            {},
        )

        if not isinstance(values, Mapping):
            continue

        for key in values:
            cleaned_key = str(key).strip()

            if not cleaned_key or cleaned_key in seen:
                continue

            seen.add(cleaned_key)
            value_keys.append(cleaned_key)

    columns = [
        ReportExceptionColumn(
            key="source_row_number",
            label="Source Row",
        ),
        ReportExceptionColumn(
            key="reason",
            label="Reason",
        ),
    ]

    columns.extend(
        ReportExceptionColumn(
            key=key,
            label=report_display_label(key),
        )
        for key in value_keys
    )

    columns.append(
        ReportExceptionColumn(
            key="source_record_id",
            label="Record ID",
        )
    )

    return tuple(columns)


def exception_cell_value(
    exception: object,
    key: str,
) -> str:
    """Return one display value from a report exception."""

    if key == "source_row_number":
        return report_display_value(
            getattr(
                exception,
                "source_row_number",
                None,
            )
        )

    if key == "source_record_id":
        return report_display_value(
            getattr(
                exception,
                "source_record_id",
                None,
            )
        )

    if key == "reason":
        return report_display_value(
            getattr(
                exception,
                "reason",
                None,
            )
        )

    values = getattr(
        exception,
        "values",
        {},
    )

    if not isinstance(values, Mapping):
        return "—"

    return report_display_value(values.get(key))


def report_exception_rate(rate: float, evaluated_count: int) -> str:
    """Display a recorded rate only when an evaluated denominator exists."""
    return f"{rate:.2f}%" if evaluated_count else "Not available: no records evaluated"
