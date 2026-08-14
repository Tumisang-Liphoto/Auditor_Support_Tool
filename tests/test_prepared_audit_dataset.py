"""Tests for prepared audit-dataset resolution and traceability."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook

from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    FieldValueStatus,
    PreparedAuditDataset,
    build_source_record_id,
    calculate_mapping_fingerprint,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
)


def create_dataset(
    tmp_path: Path,
):
    """Create a small General Ledger dataset with a skipped blank row."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"

    worksheet.append(
        [
            "Trn Dt",
            "Account No",
            "Amount",
            "Narrative",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "1000",
            125.50,
            "Weekend payment",
        ]
    )
    worksheet.append(
        [
            None,
            None,
            None,
            None,
        ]
    )
    worksheet.append(
        [
            "2026-01-05",
            "2000",
            250.00,
            "",
        ]
    )

    path = tmp_path / "prepared-audit-dataset.xlsx"
    workbook.save(path)

    package = WorkbookPackageService().build_package(path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    date_column = next(column for column in dataset.columns if column.source_column == "Trn Dt")
    account_column = next(
        column for column in dataset.columns if column.source_column == "Account No"
    )
    amount_column = next(column for column in dataset.columns if column.source_column == "Amount")
    narrative_column = next(
        column for column in dataset.columns if column.source_column == "Narrative"
    )

    date_column.confirmed_type = DetectedDataType.DATE
    account_column.confirmed_type = DetectedDataType.TEXT
    amount_column.confirmed_type = DetectedDataType.DECIMAL
    narrative_column.confirmed_type = DetectedDataType.TEXT

    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
        account_column.column_id: "account_code",
        amount_column.column_id: "transaction_amount",
        narrative_column.column_id: "transaction_description",
    }

    return (
        dataset,
        date_column,
        account_column,
        amount_column,
        narrative_column,
    )


def test_imported_rows_retain_actual_source_row_numbers(
    tmp_path: Path,
) -> None:
    """Skipped blank rows must not destroy original source-row identity."""

    dataset, *_columns = create_dataset(tmp_path)

    assert [row[SOURCE_ROW_FIELD] for row in dataset.loaded_table.rows] == [2, 4]


def test_source_record_identity_is_stable_and_dataset_scoped() -> None:
    """A source record ID should combine dataset ID and source row number."""

    assert (
        build_source_record_id(
            "dataset-abc",
            417,
        )
        == "dataset-abc:row-417"
    )


def test_iter_records_preserves_raw_rows_without_population_copy(
    tmp_path: Path,
) -> None:
    """Prepared records should wrap the existing source dictionaries."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)

    first_record = next(prepared.iter_records())

    assert first_record.raw_row is dataset.loaded_table.rows[0]
    assert first_record.source_row_number == 2
    assert first_record.source_record_id == (f"{dataset.dataset_id}:row-2")


def test_standard_field_resolves_auditee_specific_source_column(
    tmp_path: Path,
) -> None:
    """Procedures should read standard fields, not source column names."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    date_value = first_record.resolve("transaction_date")
    account_value = first_record.resolve("account_code")
    amount_value = first_record.resolve("transaction_amount")

    assert date_value.status == FieldValueStatus.VALID
    assert date_value.value == date(2026, 1, 3)

    assert account_value.status == FieldValueStatus.VALID
    assert account_value.value == "1000"

    assert amount_value.status == FieldValueStatus.VALID
    assert str(amount_value.value) == "125.5"


def test_prepared_name_change_does_not_break_standard_field_access(
    tmp_path: Path,
) -> None:
    """Field resolution must depend on stable mapping, not visible prepared name."""

    dataset, date_column, *_columns = create_dataset(tmp_path)

    date_column.confirmed_name = "Posting / Transaction Date"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.source_column == "Trn Dt"
    assert resolved.column_id == date_column.column_id


def test_blank_mapped_value_is_reported_separately(
    tmp_path: Path,
) -> None:
    """Blank values should not be silently treated as valid values."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)

    records = list(prepared.iter_records())
    second_record = records[1]

    resolved = second_record.resolve("transaction_description")

    assert resolved.status == FieldValueStatus.BLANK
    assert resolved.value is None


def test_invalid_date_is_reported_as_invalid(
    tmp_path: Path,
) -> None:
    """Invalid typed values should be distinguishable from blanks."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = "not-a-date"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None
    assert resolved.reason


def test_unmapped_field_is_reported_without_exception(
    tmp_path: Path,
) -> None:
    """Value-adding fields may be absent without breaking record access."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("entry_user")

    assert resolved.status == FieldValueStatus.UNMAPPED
    assert resolved.value is None


def test_mapping_fingerprint_is_deterministic(
    tmp_path: Path,
) -> None:
    """Unchanged mappings should always produce the same fingerprint."""

    dataset, *_columns = create_dataset(tmp_path)

    first = calculate_mapping_fingerprint(dataset)
    second = calculate_mapping_fingerprint(dataset)

    assert first == second
    assert len(first) == 64


def test_mapping_fingerprint_changes_when_mapping_changes(
    tmp_path: Path,
) -> None:
    """Mapping changes must produce a new version fingerprint."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    original = calculate_mapping_fingerprint(dataset)

    dataset.field_mappings[account_column.column_id] = "vendor_code"

    changed = calculate_mapping_fingerprint(dataset)

    assert changed != original


def test_mapping_fingerprint_changes_when_confirmed_type_changes(
    tmp_path: Path,
) -> None:
    """A type decision affects the mapping/version used by procedures."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    original = calculate_mapping_fingerprint(dataset)

    account_column.confirmed_type = DetectedDataType.INTEGER

    changed = calculate_mapping_fingerprint(dataset)

    assert changed != original
