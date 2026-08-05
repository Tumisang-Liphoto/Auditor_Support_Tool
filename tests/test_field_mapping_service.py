"""Tests for source-to-standard audit-field mapping."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.field_mapping_service import (
    FieldMappingError,
    FieldMappingService,
)
from auditor_support_tool.core.workbook_package import (
    DatasetType,
    FieldMappingStatus,
    PreparationStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)


def create_general_ledger_dataset(
    tmp_path: Path,
) -> WorksheetDataset:
    """Create a prepared General Ledger dataset."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"

    worksheet.append(
        [
            "Transaction Date",
            "Account Code",
            "Description",
            "Amount",
            "Invoice Number",
        ]
    )
    worksheet.append(
        [
            "2026-01-01",
            "1000",
            "Payment",
            250.00,
            "INV-001",
        ]
    )

    path = tmp_path / "mapping.xlsx"
    workbook.save(path)

    package = WorkbookPackageService().build_package(path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    dataset.selected = True
    dataset.status = PreparationStatus.CONFIRMED
    dataset.confirmed_dataset_type = DatasetType.GENERAL_LEDGER
    dataset.preparation_status = PreparationStatus.CONFIRMED

    return dataset


def test_general_ledger_catalogue_is_available(
    tmp_path: Path,
) -> None:
    """The service should return General Ledger fields."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    field_keys = {field.key for field in service.available_fields(dataset)}

    assert "transaction_date" in field_keys
    assert "account_code" in field_keys
    assert "invoice_number" in field_keys


def test_mapping_can_be_assigned(
    tmp_path: Path,
) -> None:
    """An included source column can be mapped."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    service.assign_mapping(
        dataset,
        "Transaction Date",
        "transaction_date",
    )

    assert dataset.field_mappings["Transaction Date"] == "transaction_date"
    assert dataset.mapping_status == FieldMappingStatus.IN_PROGRESS


def test_mapping_requires_prepared_dataset(
    tmp_path: Path,
) -> None:
    """Field mapping cannot start before preparation."""

    dataset = create_general_ledger_dataset(tmp_path)
    dataset.preparation_status = PreparationStatus.NOT_REVIEWED

    service = FieldMappingService()

    with pytest.raises(
        FieldMappingError,
        match="Complete Data Preparation",
    ):
        service.assign_mapping(
            dataset,
            "Transaction Date",
            "transaction_date",
        )


def test_excluded_column_cannot_be_mapped(
    tmp_path: Path,
) -> None:
    """Excluded prepared columns cannot be mapped."""

    dataset = create_general_ledger_dataset(tmp_path)

    transaction_column = next(
        column for column in dataset.columns if column.source_column == "Transaction Date"
    )
    transaction_column.included = False

    service = FieldMappingService()

    with pytest.raises(
        FieldMappingError,
        match="not an included prepared column",
    ):
        service.assign_mapping(
            dataset,
            "Transaction Date",
            "transaction_date",
        )


def test_unknown_standard_field_is_rejected(
    tmp_path: Path,
) -> None:
    """Mappings must use the dataset catalogue."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    with pytest.raises(
        FieldMappingError,
        match="not a recognised standard field",
    ):
        service.assign_mapping(
            dataset,
            "Transaction Date",
            "unknown_field",
        )


def test_standard_field_cannot_be_mapped_twice(
    tmp_path: Path,
) -> None:
    """One standard field cannot be assigned twice."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    service.assign_mapping(
        dataset,
        "Transaction Date",
        "transaction_date",
    )

    with pytest.raises(
        FieldMappingError,
        match="already mapped",
    ):
        service.assign_mapping(
            dataset,
            "Description",
            "transaction_date",
        )


def test_mapping_can_be_removed(
    tmp_path: Path,
) -> None:
    """A mapping can be cleared from a source column."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    service.assign_mapping(
        dataset,
        "Transaction Date",
        "transaction_date",
    )
    service.remove_mapping(
        dataset,
        "Transaction Date",
    )

    assert not dataset.field_mappings
    assert dataset.mapping_status == FieldMappingStatus.NOT_STARTED


def test_no_global_required_fields_are_reported(
    tmp_path: Path,
) -> None:
    """Field mapping should not impose global required fields."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    missing_fields = service.missing_required_fields(dataset)

    assert missing_fields == ()


def test_confirmation_does_not_require_specific_standard_fields(
    tmp_path: Path,
) -> None:
    """A dataset may be confirmed without predefined required mappings."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    service.assign_mapping(
        dataset,
        "Transaction Date",
        "transaction_date",
    )

    status = service.confirm_dataset(dataset)

    assert status == FieldMappingStatus.CONFIRMED
    assert dataset.mapping_status == FieldMappingStatus.CONFIRMED


def test_dataset_can_be_confirmed(
    tmp_path: Path,
) -> None:
    """A valid mapping can be confirmed."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    service.assign_mapping(
        dataset,
        "Transaction Date",
        "transaction_date",
    )
    service.assign_mapping(
        dataset,
        "Account Code",
        "account_code",
    )

    status = service.confirm_dataset(dataset)

    assert status == FieldMappingStatus.CONFIRMED


def test_reset_removes_all_mappings(
    tmp_path: Path,
) -> None:
    """Reset should return mapping to its initial state."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    service.assign_mapping(
        dataset,
        "Transaction Date",
        "transaction_date",
    )
    service.assign_mapping(
        dataset,
        "Account Code",
        "account_code",
    )

    service.reset_dataset(dataset)

    assert not dataset.field_mappings
    assert dataset.mapping_status == FieldMappingStatus.NOT_STARTED


def test_dataset_without_catalogue_is_not_applicable(
    tmp_path: Path,
) -> None:
    """Unsupported dataset types should not block workflow."""

    dataset = create_general_ledger_dataset(tmp_path)
    dataset.confirmed_dataset_type = DatasetType.OTHER

    service = FieldMappingService()

    status = service.confirm_dataset(dataset)

    assert status == FieldMappingStatus.NOT_APPLICABLE
