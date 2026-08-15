"""Tests for the generic audit-record source contract."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from auditor_support_tool.core.audit_record_source import (
    AuditRecord,
    AuditRecordSource,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)


def create_prepared_dataset(
    tmp_path: Path,
) -> PreparedAuditDataset:
    """Create a small prepared dataset for contract testing."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Audit_Data"

    worksheet.append(
        [
            "Date",
            "Reference",
            "Amount",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "REF-001",
            125.00,
        ]
    )
    worksheet.append(
        [
            "2026-01-05",
            "REF-002",
            250.00,
        ]
    )

    source_path = tmp_path / "audit-record-source.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)

    dataset = package.get_dataset_by_worksheet("Audit_Data")

    assert dataset is not None

    date_column = next(column for column in dataset.columns if column.source_column == "Date")

    reference_column = next(
        column for column in dataset.columns if column.source_column == "Reference"
    )

    amount_column = next(column for column in dataset.columns if column.source_column == "Amount")

    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
        reference_column.column_id: "reference",
        amount_column.column_id: "amount",
    }

    return PreparedAuditDataset(dataset)


def test_prepared_dataset_satisfies_record_source_contract(
    tmp_path: Path,
) -> None:
    """PreparedAuditDataset should implement AuditRecordSource structurally."""

    prepared = create_prepared_dataset(tmp_path)

    assert isinstance(
        prepared,
        AuditRecordSource,
    )


def test_prepared_records_satisfy_record_contract(
    tmp_path: Path,
) -> None:
    """PreparedAuditRecord should implement AuditRecord structurally."""

    prepared = create_prepared_dataset(tmp_path)

    record = next(prepared.iter_records())

    assert isinstance(
        record,
        AuditRecord,
    )


def test_record_source_exposes_generic_dataset_information(
    tmp_path: Path,
) -> None:
    """The source contract should expose generic execution metadata."""

    prepared = create_prepared_dataset(tmp_path)

    assert prepared.dataset_id
    assert prepared.record_count == 2
    assert prepared.mapping_fingerprint

    assert prepared.standard_fields == (
        "amount",
        "reference",
        "transaction_date",
    )


def test_record_source_reports_available_standard_fields(
    tmp_path: Path,
) -> None:
    """Procedures should be able to check field availability generically."""

    prepared = create_prepared_dataset(tmp_path)

    assert prepared.has_field("transaction_date")
    assert prepared.has_field("amount")
    assert not prepared.has_field("invoice_number")


def test_record_source_iterates_complete_population(
    tmp_path: Path,
) -> None:
    """Record-source iteration should expose every prepared record."""

    prepared = create_prepared_dataset(tmp_path)

    records = tuple(prepared.iter_records())

    assert len(records) == 2
    assert len(records) == prepared.record_count

    assert records[0].source_row_number == 2
    assert records[1].source_row_number == 3

    assert records[0].source_record_id
    assert records[1].source_record_id


def test_record_values_use_standard_field_names(
    tmp_path: Path,
) -> None:
    """Procedure logic should access mapped fields rather than source columns."""

    prepared = create_prepared_dataset(tmp_path)

    record = next(prepared.iter_records())

    assert record.value("reference") == "REF-001"
    assert record.value("amount") is not None

    assert (
        record.value(
            "field_that_is_not_mapped",
            default="missing",
        )
        == "missing"
    )
