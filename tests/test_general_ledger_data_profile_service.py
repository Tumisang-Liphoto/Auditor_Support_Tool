"""Tests for profiling received General Ledger data."""

from datetime import date
from pathlib import Path

import pytest

from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_service import (
    DataProfileService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
    LoadedTable,
    PopulationSummary,
)


@pytest.fixture
def table() -> LoadedTable:
    """Return a representative received population."""

    headers = (
        "Transaction Date",
        "Invoice Number",
        "Vendor Number",
        "Amount",
        "Approved",
        "Notes",
    )

    rows = (
        {
            "Transaction Date": date(2026, 1, 10),
            "Invoice Number": "INV-001",
            "Vendor Number": "V001",
            "Amount": 100.00,
            "Approved": True,
            "Notes": "First record",
            SOURCE_ROW_FIELD: 2,
        },
        {
            "Transaction Date": date(2026, 1, 11),
            "Invoice Number": "INV-002",
            "Vendor Number": "V002",
            "Amount": 250.00,
            "Approved": False,
            "Notes": None,
            SOURCE_ROW_FIELD: 3,
        },
        {
            "Transaction Date": date(2026, 1, 12),
            "Invoice Number": "inv-001",
            "Vendor Number": "V001",
            "Amount": 100.00,
            "Approved": True,
            "Notes": "   ",
            SOURCE_ROW_FIELD: 4,
        },
    )

    return LoadedTable(
        source_path=Path("sample.xlsx"),
        file_type="xlsx",
        worksheet_name="General_Ledger",
        headers=headers,
        original_headers=headers,
        rows=rows,
        summary=PopulationSummary(
            source_records_read=3,
            records_loaded=3,
            blank_rows_skipped=0,
            column_count=6,
            blank_cell_count=2,
            header_changes=(),
        ),
    )


def test_population_profile_contains_source_summary(
    table: LoadedTable,
) -> None:
    """The profile should retain population-level information."""

    profile = DataProfileService().profile(table)

    assert profile.source_file == "sample.xlsx"
    assert profile.worksheet_name == "General_Ledger"
    assert profile.record_count == 3
    assert profile.column_count == 6
    assert profile.blank_cell_count == 2
    assert profile.completely_blank_rows_skipped == 0


def test_profile_contains_one_entry_per_source_column(
    table: LoadedTable,
) -> None:
    """Every uploaded source column should be profiled."""

    profile = DataProfileService().profile(table)

    assert len(profile.columns) == 6

    assert tuple(column.column_name for column in profile.columns) == table.headers


def test_date_column_is_detected(
    table: LoadedTable,
) -> None:
    """Date values should be classified as dates."""

    profile = DataProfileService().profile(table)

    transaction_date = profile.columns[0]

    assert transaction_date.detected_type == DetectedDataType.DATE
    assert transaction_date.minimum_value == date(2026, 1, 10)
    assert transaction_date.maximum_value == date(2026, 1, 12)


def test_decimal_column_is_detected(
    table: LoadedTable,
) -> None:
    """Monetary values should be classified as decimal values."""

    profile = DataProfileService().profile(table)

    amount = profile.columns[3]

    assert amount.detected_type == DetectedDataType.DECIMAL
    assert amount.minimum_value == 100.00
    assert amount.maximum_value == 250.00


def test_boolean_column_is_detected(
    table: LoadedTable,
) -> None:
    """Boolean source fields should not be treated as integers."""

    profile = DataProfileService().profile(table)

    approved = profile.columns[4]

    assert approved.detected_type == DetectedDataType.BOOLEAN
    assert approved.distinct_values == 2


def test_blank_values_are_counted(
    table: LoadedTable,
) -> None:
    """Null and whitespace-only values should count as blank."""

    profile = DataProfileService().profile(table)

    notes = profile.columns[5]

    assert notes.total_records == 3
    assert notes.populated_records == 1
    assert notes.blank_records == 2
    assert notes.completeness_percentage == 33.33


def test_text_distinct_values_ignore_case_and_outer_spaces(
    table: LoadedTable,
) -> None:
    """Equivalent text values should use one comparison form."""

    profile = DataProfileService().profile(table)

    invoice_number = profile.columns[1]

    assert invoice_number.distinct_values == 2
    assert invoice_number.duplicate_values == 1


def test_population_column_completeness_counts(
    table: LoadedTable,
) -> None:
    """The profile should count complete and incomplete columns."""

    profile = DataProfileService().profile(table)

    assert profile.columns_with_blanks == 1
    assert profile.fully_populated_columns == 5


def test_sample_values_are_distinct_and_limited(
    table: LoadedTable,
) -> None:
    """Displayed sample values should be distinct and controlled."""

    profile = DataProfileService().profile(
        table,
        sample_limit=2,
    )

    invoice_number = profile.columns[1]

    assert invoice_number.sample_values == (
        "INV-001",
        "INV-002",
    )


def test_invalid_sample_limit_is_rejected(
    table: LoadedTable,
) -> None:
    """At least one sample value must be requested."""

    with pytest.raises(
        ValueError,
        match="sample-value limit must be at least 1",
    ):
        DataProfileService().profile(
            table,
            sample_limit=0,
        )
