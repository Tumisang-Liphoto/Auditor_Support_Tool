"""Tests for General Ledger field mapping and test availability."""

from pathlib import Path

import pytest

from auditor_support_tool.domains.financial_audit.general_ledger.field_mapping_service import (
    FieldMappingError,
    FieldMappingService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
    PopulationSummary,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_definitions import (
    GL_001_DUPLICATE_INVOICES,
    GL_003_WEEKEND_POSTINGS,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    FieldMapping,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    TestAvailabilityStatus as AuditTestAvailabilityStatus,
)


@pytest.fixture
def table() -> LoadedTable:
    """Return a representative General Ledger population."""

    return LoadedTable(
        source_path=Path("sample.xlsx"),
        file_type="xlsx",
        worksheet_name="General_Ledger",
        headers=(
            "Transaction Date",
            "Invoice Number",
            "Vendor Number",
            "Amount",
        ),
        original_headers=(
            "Transaction Date",
            "Invoice Number",
            "Vendor Number",
            "Amount",
        ),
        rows=(
            {
                "Transaction Date": "2026-01-05",
                "Invoice Number": "INV-001",
                "Vendor Number": "V001",
                "Amount": 100.00,
                "_source_row_number": 2,
            },
        ),
        summary=PopulationSummary(
            source_records_read=1,
            records_loaded=1,
            blank_rows_skipped=0,
            column_count=4,
            blank_cell_count=0,
            header_changes=(),
        ),
    )


@pytest.fixture
def service() -> FieldMappingService:
    """Return a field-mapping service."""

    return FieldMappingService()


def test_valid_mappings_are_returned(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """Known fields and source columns should validate."""

    mappings = service.validate_mappings(
        table,
        (
            FieldMapping(
                standard_field="transaction_date",
                source_column="Transaction Date",
            ),
            FieldMapping(
                standard_field="invoice_number",
                source_column="Invoice Number",
            ),
        ),
    )

    assert len(mappings) == 2
    assert mappings[0].standard_field == "transaction_date"
    assert mappings[1].source_column == "Invoice Number"


def test_unknown_standard_field_is_rejected(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """Mappings may only use registered standard fields."""

    with pytest.raises(
        FieldMappingError,
        match="Unknown standard field",
    ):
        service.validate_mappings(
            table,
            (
                FieldMapping(
                    standard_field="unknown_field",
                    source_column="Invoice Number",
                ),
            ),
        )


def test_missing_source_column_is_rejected(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """Mappings may only use columns in the population."""

    with pytest.raises(
        FieldMappingError,
        match="Source column not found",
    ):
        service.validate_mappings(
            table,
            (
                FieldMapping(
                    standard_field="invoice_number",
                    source_column="Missing Column",
                ),
            ),
        )


def test_standard_field_cannot_be_mapped_twice(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """Each standard field should map to one source column."""

    with pytest.raises(
        FieldMappingError,
        match="Standard field mapped more than once",
    ):
        service.validate_mappings(
            table,
            (
                FieldMapping(
                    standard_field="invoice_number",
                    source_column="Invoice Number",
                ),
                FieldMapping(
                    standard_field="invoice_number",
                    source_column="Vendor Number",
                ),
            ),
        )


def test_source_column_cannot_be_mapped_twice(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """One source column should not represent multiple fields."""

    with pytest.raises(
        FieldMappingError,
        match="Source column mapped more than once",
    ):
        service.validate_mappings(
            table,
            (
                FieldMapping(
                    standard_field="invoice_number",
                    source_column="Invoice Number",
                ),
                FieldMapping(
                    standard_field="vendor_number",
                    source_column="Invoice Number",
                ),
            ),
        )


def test_gl_001_available_when_invoice_number_is_mapped(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """GL-001 should run when invoice number is mapped."""

    availability = service.check_test_availability(
        table,
        (
            FieldMapping(
                standard_field="invoice_number",
                source_column="Invoice Number",
            ),
            FieldMapping(
                standard_field="vendor_number",
                source_column="Vendor Number",
            ),
        ),
        GL_001_DUPLICATE_INVOICES,
    )

    assert availability.status == AuditTestAvailabilityStatus.AVAILABLE
    assert availability.can_run is True
    assert availability.missing_required_fields == ()
    assert availability.mapped_required_fields == ("invoice_number",)
    assert "vendor_number" in availability.mapped_helpful_fields


def test_gl_001_unavailable_without_invoice_number(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """GL-001 should not run without invoice number."""

    availability = service.check_test_availability(
        table,
        (
            FieldMapping(
                standard_field="vendor_number",
                source_column="Vendor Number",
            ),
        ),
        GL_001_DUPLICATE_INVOICES,
    )

    assert availability.status == AuditTestAvailabilityStatus.UNAVAILABLE
    assert availability.can_run is False
    assert availability.missing_required_fields == ("invoice_number",)


def test_gl_003_available_when_transaction_date_is_mapped(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """GL-003 should run when transaction date is mapped."""

    availability = service.check_test_availability(
        table,
        (
            FieldMapping(
                standard_field="transaction_date",
                source_column="Transaction Date",
            ),
            FieldMapping(
                standard_field="net_amount",
                source_column="Amount",
            ),
        ),
        GL_003_WEEKEND_POSTINGS,
    )

    assert availability.status == AuditTestAvailabilityStatus.AVAILABLE
    assert availability.can_run is True
    assert availability.mapped_required_fields == ("transaction_date",)
    assert "net_amount" in availability.mapped_helpful_fields


def test_available_with_warning_when_no_helpful_fields_are_mapped(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """A test can run with only its required field."""

    availability = service.check_test_availability(
        table,
        (
            FieldMapping(
                standard_field="transaction_date",
                source_column="Transaction Date",
            ),
        ),
        GL_003_WEEKEND_POSTINGS,
    )

    assert availability.status == AuditTestAvailabilityStatus.AVAILABLE_WITH_WARNING
    assert availability.can_run is True
    assert len(availability.warnings) == 1


def test_all_registered_tests_are_checked(
    service: FieldMappingService,
    table: LoadedTable,
) -> None:
    """Availability checks should include GL-001 and GL-003."""

    results = service.check_all_tests(
        table,
        (
            FieldMapping(
                standard_field="transaction_date",
                source_column="Transaction Date",
            ),
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
        ),
    )

    results_by_code = {result.test_code: result for result in results}

    assert set(results_by_code) == {
        "GL-001",
        "GL-003",
    }
    assert results_by_code["GL-001"].can_run is True
    assert results_by_code["GL-003"].can_run is True
