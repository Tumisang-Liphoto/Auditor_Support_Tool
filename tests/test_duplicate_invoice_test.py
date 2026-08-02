"""Tests for GL-001 Duplicate Invoice Detection."""

from pathlib import Path

import pytest

from auditor_support_tool.domains.financial_audit.general_ledger.duplicate_invoice_test import (
    EXCEPTION_REASON,
    DuplicateInvoiceTest,
    DuplicateInvoiceTestError,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
    LoadedTable,
    PopulationSummary,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    FieldMapping,
)


def make_table(
    rows: tuple[dict[str, object], ...],
) -> LoadedTable:
    """Create a loaded table for duplicate-invoice testing."""

    headers = (
        "Invoice Number",
        "Vendor Number",
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
    """Return the mappings used by most GL-001 tests."""

    return (
        FieldMapping(
            standard_field="invoice_number",
            source_column="Invoice Number",
        ),
        FieldMapping(
            standard_field="vendor_number",
            source_column="Vendor Number",
        ),
        FieldMapping(
            standard_field="net_amount",
            source_column="Amount",
        ),
    )


def test_repeated_invoice_numbers_are_flagged() -> None:
    """Every record in a repeated-invoice group should be returned."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "INV-002",
                "Vendor Number": "V002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("duplicate_groups") == 1
    assert result.metric_value("flagged_records") == 2
    assert result.metric_value("additional_duplicate_records") == 1
    assert result.exception_count == 2

    assert {exception.source_row_number for exception in result.exceptions} == {
        2,
        4,
    }

    assert {exception.group_id for exception in result.exceptions} == {
        "GL-001-GROUP-0001",
    }

    assert all(exception.reason == EXCEPTION_REASON for exception in result.exceptions)


def test_invoice_comparison_ignores_case_and_outer_spaces() -> None:
    """Case and surrounding spaces should not conceal repeated invoices."""

    table = make_table(
        (
            {
                "Invoice Number": " INV-100 ",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "inv-100",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("duplicate_groups") == 1
    assert result.metric_value("flagged_records") == 2

    assert all(
        exception.derived_values["normalised_invoice_number"] == "inv-100"
        for exception in result.exceptions
    )


def test_blank_invoice_numbers_are_excluded() -> None:
    """Blank invoice numbers should not form duplicate groups."""

    table = make_table(
        (
            {
                "Invoice Number": None,
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "   ",
                "Vendor Number": "V002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V003",
                "Amount": 300.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.records_tested == 1
    assert result.records_excluded == 2
    assert result.metric_value("duplicate_groups") == 0
    assert result.exception_count == 0

    assert len(result.data_quality_issues) == 2

    assert {issue.source_row_number for issue in result.data_quality_issues} == {
        2,
        3,
    }


def test_same_vendor_group_is_identified() -> None:
    """Repeated invoices for one vendor should be classified."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "v001",
                "Amount": 150.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("same_vendor_groups") == 1
    assert result.metric_value("multiple_vendor_groups") == 0

    assert all(
        exception.derived_values["vendor_relationship"] == "Same vendor"
        for exception in result.exceptions
    )


def test_multiple_vendor_group_is_identified() -> None:
    """The result should distinguish invoice reuse across vendors."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V002",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("same_vendor_groups") == 0
    assert result.metric_value("multiple_vendor_groups") == 1

    assert all(
        exception.derived_values["vendor_relationship"] == "Multiple vendors"
        for exception in result.exceptions
    )


def test_missing_vendor_value_makes_relationship_not_assessable() -> None:
    """Partially blank vendor information should not be treated as same vendor."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": None,
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("vendor_not_assessable_groups") == 1

    assert all(
        exception.derived_values["vendor_relationship"] == "Not assessable"
        for exception in result.exceptions
    )


def test_three_record_group_counts_additional_duplicates() -> None:
    """A group of three should contain two additional records."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 3,
            },
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 4,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("duplicate_groups") == 1
    assert result.metric_value("flagged_records") == 3
    assert result.metric_value("additional_duplicate_records") == 2


def test_unique_invoice_numbers_produce_no_exceptions() -> None:
    """Unique invoice numbers should return no flags."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
            {
                "Invoice Number": "INV-002",
                "Vendor Number": "V002",
                "Amount": 200.00,
                SOURCE_ROW_FIELD: 3,
            },
        )
    )

    result = DuplicateInvoiceTest().run(
        table,
        mappings(),
    )

    assert result.metric_value("duplicate_groups") == 0
    assert result.metric_value("flagged_records") == 0
    assert result.exception_count == 0


def test_missing_invoice_mapping_is_rejected() -> None:
    """GL-001 should not run without invoice-number mapping."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: 2,
            },
        )
    )

    with pytest.raises(
        DuplicateInvoiceTestError,
        match="requires a mapped invoice-number field",
    ):
        DuplicateInvoiceTest().run(
            table,
            (
                FieldMapping(
                    standard_field="vendor_number",
                    source_column="Vendor Number",
                ),
            ),
        )


def test_invalid_source_row_number_is_rejected() -> None:
    """Every record must retain a valid source row number."""

    table = make_table(
        (
            {
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                SOURCE_ROW_FIELD: "Row 2",
            },
        )
    )

    with pytest.raises(
        DuplicateInvoiceTestError,
        match="no valid source row number",
    ):
        DuplicateInvoiceTest().run(
            table,
            mappings(),
        )
