"""Tests for generic human-readable audit report formatting."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from auditor_support_tool.presentation.audit_procedure_report_formatter import (
    build_exception_columns,
    exception_cell_value,
    report_display_label,
    report_display_value,
)


@dataclass(frozen=True)
class StubException:
    source_record_id: str
    source_row_number: int
    reason: str
    values: dict[str, object]


def test_report_display_label_formats_machine_keys() -> None:
    assert report_display_label("transaction_amount") == "Transaction Amount"
    assert report_display_label("source_record_id") == "Source Record ID"
    assert report_display_label("source_sha256") == "Source SHA-256"


def test_report_display_value_formats_common_types() -> None:
    assert report_display_value(None) == "—"
    assert report_display_value(True) == "Yes"
    assert report_display_value(False) == "No"
    assert report_display_value(12500) == "12,500"
    assert report_display_value(12.345) == "12.35"
    assert report_display_value(Decimal("125.50")) == "125.50"
    assert report_display_value(date(2026, 8, 31)) == "31 Aug 2026"
    assert (
        report_display_value(
            datetime(
                2026,
                8,
                31,
                14,
                5,
            )
        )
        == "31 Aug 2026, 14:05"
    )


def test_report_display_value_formats_sequences() -> None:
    assert (
        report_display_value(
            (
                "Saturday",
                "Sunday",
            )
        )
        == "Saturday, Sunday"
    )


def test_exception_columns_include_complete_union_of_values() -> None:
    exceptions = (
        StubException(
            source_record_id="a:1",
            source_row_number=1,
            reason="First",
            values={
                "journal_number": "J001",
                "entry_user": "user.a",
            },
        ),
        StubException(
            source_record_id="a:2",
            source_row_number=2,
            reason="Second",
            values={
                "entry_user": "user.b",
                "approval_user": "user.b",
            },
        ),
    )

    columns = build_exception_columns(exceptions)

    assert tuple(column.key for column in columns) == (
        "source_row_number",
        "reason",
        "journal_number",
        "entry_user",
        "approval_user",
        "source_record_id",
    )


def test_exception_columns_preserve_first_seen_field_order() -> None:
    exceptions = (
        StubException(
            source_record_id="a:1",
            source_row_number=1,
            reason="First",
            values={
                "vendor_code": "V001",
                "invoice_number": "INV1",
            },
        ),
        StubException(
            source_record_id="a:2",
            source_row_number=2,
            reason="Second",
            values={
                "invoice_number": "INV2",
                "account_code": "6000",
            },
        ),
    )

    assert tuple(column.key for column in build_exception_columns(exceptions)) == (
        "source_row_number",
        "reason",
        "vendor_code",
        "invoice_number",
        "account_code",
        "source_record_id",
    )


def test_exception_cell_value_reads_base_and_dynamic_fields() -> None:
    exception = StubException(
        source_record_id="dataset:44",
        source_row_number=44,
        reason="Requires review.",
        values={
            "amount": Decimal("1000.25"),
        },
    )

    assert (
        exception_cell_value(
            exception,
            "source_row_number",
        )
        == "44"
    )
    assert (
        exception_cell_value(
            exception,
            "reason",
        )
        == "Requires review."
    )
    assert (
        exception_cell_value(
            exception,
            "source_record_id",
        )
        == "dataset:44"
    )
    assert (
        exception_cell_value(
            exception,
            "amount",
        )
        == "1000.25"
    )


def test_exception_cell_value_returns_dash_for_missing_field() -> None:
    exception = StubException(
        source_record_id="dataset:1",
        source_row_number=1,
        reason="Reason",
        values={},
    )

    assert (
        exception_cell_value(
            exception,
            "missing_field",
        )
        == "—"
    )
