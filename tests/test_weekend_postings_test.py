"""Tests for GL-003 Weekend Postings."""

from datetime import date, datetime
from pathlib import Path

import pytest

from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
    LoadedTable,
    PopulationSummary,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    FieldMapping,
)
from auditor_support_tool.domains.financial_audit.general_ledger.weekend_postings_test import (
    WeekendPostingsTest,
    WeekendPostingsTestError,
)


def make_table(
    rows: tuple[dict[str, object], ...],
) -> LoadedTable:
    """Create a loaded table for weekend-posting testing."""

    headers = (
        "Transaction Date",
        "Journal Number",
        "Amount",
    )

    return LoadedTable(
        source_path=Path("sample.xlsx"),
        file_type="xlsx",
        worksheet_name="General_Ledger",
        headers=headers,
        original_headers=headers,
        rows=rows,
        summary=PopulationSummary(
            source_records_read=len(rows),
            records_loaded=len(rows),
            blank_rows_skipped=0,
            column_count=len(headers),
            blank_cell_count=0,
            header_changes=(),
        ),
    )


def mappings() -> tuple[FieldMapping, ...]:
    """Return mappings used by most GL-003 tests."""

    return (
        FieldMapping(
            standard_field="transaction_date",
            source_column="Transaction Date",
        ),
        FieldMapping(
            standard_field="journal_number",
            source_column="Journal Number",
        ),
        FieldMapping(
            standard_field="net_amount",
            source_column="Amount",
        ),
    )


def test_saturday_and_sunday_postings_are_flagged() -> None:
    """Saturday and Sunday transactions should be returned."""

    table = make_table(
        (
            {
                "Transaction Date": date(2026, 1, 10),
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Transaction Date": date(2026, 1, 11),
                "Journal Number": "J002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Transaction Date": date(2026, 1, 12),
                "Journal Number": "J003",
                "Amount": 300.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("weekend_postings") == 2
    assert result.metric_value("saturday_postings") == 1
    assert result.metric_value("sunday_postings") == 1
    assert result.metric_value("distinct_weekend_dates") == 2
    assert result.exception_count == 2

    assert {exception.source_row_number for exception in result.exceptions} == {
        2,
        3,
    }


def test_weekday_postings_are_not_flagged() -> None:
    """Monday-to-Friday transactions should not be exceptions."""

    table = make_table(
        (
            {
                "Transaction Date": date(2026, 1, 12),
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Transaction Date": date(2026, 1, 13),
                "Journal Number": "J002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("weekend_postings") == 0
    assert result.metric_value("saturday_postings") == 0
    assert result.metric_value("sunday_postings") == 0
    assert result.exception_count == 0


def test_datetime_values_are_supported() -> None:
    """Excel datetime values should be reduced to calendar dates."""

    table = make_table(
        (
            {
                "Transaction Date": datetime(
                    2026,
                    1,
                    10,
                    14,
                    30,
                ),
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("weekend_postings") == 1
    assert result.exceptions[0].derived_values["parsed_transaction_date"] == "2026-01-10"
    assert result.exceptions[0].derived_values["day_of_week"] == "Saturday"


@pytest.mark.parametrize(
    ("source_value", "expected_date"),
    (
        ("2026-01-10", "2026-01-10"),
        ("2026/01/10", "2026-01-10"),
        ("10/01/2026", "2026-01-10"),
        ("10-01-2026", "2026-01-10"),
        ("10 Jan 2026", "2026-01-10"),
        ("10 January 2026", "2026-01-10"),
        ("2026-01-10 08:30:00", "2026-01-10"),
    ),
)
def test_supported_text_date_formats_are_parsed(
    source_value: str,
    expected_date: str,
) -> None:
    """Common source date formats should be interpreted."""

    table = make_table(
        (
            {
                "Transaction Date": source_value,
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("weekend_postings") == 1
    assert result.exceptions[0].derived_values["parsed_transaction_date"] == expected_date


def test_blank_dates_are_excluded_and_reported() -> None:
    """Blank dates should be reported as data-quality issues."""

    table = make_table(
        (
            {
                "Transaction Date": None,
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Transaction Date": "   ",
                "Journal Number": "J002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Transaction Date": "2026-01-10",
                "Journal Number": "J003",
                "Amount": 300.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("blank_dates") == 2
    assert result.metric_value("invalid_dates") == 0
    assert result.records_excluded == 2
    assert result.records_tested == 1
    assert len(result.data_quality_issues) == 2

    assert {issue.issue_type for issue in result.data_quality_issues} == {
        "blank_transaction_date",
    }


def test_invalid_dates_are_excluded_and_reported() -> None:
    """Unusable dates should be reported separately from blanks."""

    table = make_table(
        (
            {
                "Transaction Date": "not-a-date",
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Transaction Date": 12345,
                "Journal Number": "J002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Transaction Date": "2026-01-11",
                "Journal Number": "J003",
                "Amount": 300.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("invalid_dates") == 2
    assert result.metric_value("blank_dates") == 0
    assert result.records_excluded == 2
    assert result.records_tested == 1
    assert result.metric_value("sunday_postings") == 1

    assert {issue.issue_type for issue in result.data_quality_issues} == {
        "invalid_transaction_date",
    }


def test_distinct_weekend_dates_are_counted_once() -> None:
    """Several postings on one weekend date should count as one date."""

    table = make_table(
        (
            {
                "Transaction Date": "2026-01-10",
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Transaction Date": "2026-01-10",
                "Journal Number": "J002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Transaction Date": "2026-01-11",
                "Journal Number": "J003",
                "Amount": 300.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("weekend_postings") == 3
    assert result.metric_value("distinct_weekend_dates") == 2


def test_exception_wording_includes_day_name() -> None:
    """Each exception should identify Saturday or Sunday."""

    table = make_table(
        (
            {
                "Transaction Date": "2026-01-10",
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Transaction Date": "2026-01-11",
                "Journal Number": "J002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = WeekendPostingsTest().run(
        table,
        mappings(),
    )

    assert result.exceptions[0].reason == ("Weekend posting: Saturday — further scrutiny required.")
    assert result.exceptions[1].reason == ("Weekend posting: Sunday — further scrutiny required.")


def test_missing_transaction_date_mapping_is_rejected() -> None:
    """GL-003 should not run without transaction-date mapping."""

    table = make_table(
        (
            {
                "Transaction Date": "2026-01-10",
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
        )
    )

    with pytest.raises(
        WeekendPostingsTestError,
        match="requires a mapped transaction-date field",
    ):
        WeekendPostingsTest().run(
            table,
            (
                FieldMapping(
                    standard_field="journal_number",
                    source_column="Journal Number",
                ),
            ),
        )


def test_invalid_source_row_number_is_rejected() -> None:
    """Every record must retain a valid source row number."""

    table = make_table(
        (
            {
                "Transaction Date": "2026-01-10",
                "Journal Number": "J001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: "Row 2",
            },
        )
    )

    with pytest.raises(
        WeekendPostingsTestError,
        match="no valid source row number",
    ):
        WeekendPostingsTest().run(
            table,
            mappings(),
        )
