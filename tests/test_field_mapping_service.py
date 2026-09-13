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
    PreparedColumn,
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


def column_by_source(
    dataset: WorksheetDataset,
    source_column: str,
) -> PreparedColumn:
    """Return a prepared column by its original source-column name."""

    column = next(
        (candidate for candidate in dataset.columns if candidate.source_column == source_column),
        None,
    )

    assert column is not None

    return column


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
    """An included prepared column can be mapped."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()
    transaction_column = column_by_source(dataset, "Transaction Date")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )

    assert dataset.field_mappings[transaction_column.column_id] == "transaction_date"
    assert dataset.mapping_status == FieldMappingStatus.IN_PROGRESS


def test_mapping_requires_prepared_dataset(
    tmp_path: Path,
) -> None:
    """Field mapping cannot start before preparation."""

    dataset = create_general_ledger_dataset(tmp_path)
    dataset.preparation_status = PreparationStatus.NOT_REVIEWED
    transaction_column = column_by_source(dataset, "Transaction Date")

    service = FieldMappingService()

    with pytest.raises(
        FieldMappingError,
        match="Complete Data Preparation",
    ):
        service.assign_mapping(
            dataset,
            transaction_column.column_id,
            "transaction_date",
        )


def test_excluded_column_cannot_be_mapped(
    tmp_path: Path,
) -> None:
    """Excluded prepared columns cannot be mapped."""

    dataset = create_general_ledger_dataset(tmp_path)

    transaction_column = column_by_source(dataset, "Transaction Date")
    transaction_column.included = False

    service = FieldMappingService()

    with pytest.raises(
        FieldMappingError,
        match="not available",
    ):
        service.assign_mapping(
            dataset,
            transaction_column.column_id,
            "transaction_date",
        )


def test_unknown_standard_field_is_rejected(
    tmp_path: Path,
) -> None:
    """Mappings must use the dataset catalogue."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()
    transaction_column = column_by_source(dataset, "Transaction Date")

    with pytest.raises(
        FieldMappingError,
        match="not a recognised standard field",
    ):
        service.assign_mapping(
            dataset,
            transaction_column.column_id,
            "unknown_field",
        )


def test_standard_field_cannot_be_mapped_twice(
    tmp_path: Path,
) -> None:
    """One standard field cannot be assigned twice."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")
    description_column = column_by_source(dataset, "Description")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )

    with pytest.raises(
        FieldMappingError,
        match="already mapped",
    ):
        service.assign_mapping(
            dataset,
            description_column.column_id,
            "transaction_date",
        )


def test_mapping_can_be_removed(
    tmp_path: Path,
) -> None:
    """A mapping can be cleared from a prepared column."""

    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()
    transaction_column = column_by_source(dataset, "Transaction Date")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )
    service.remove_mapping(
        dataset,
        transaction_column.column_id,
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
    transaction_column = column_by_source(dataset, "Transaction Date")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
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

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )
    service.assign_mapping(
        dataset,
        account_column.column_id,
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

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )
    service.assign_mapping(
        dataset,
        account_column.column_id,
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

def test_suggest_mappings_applies_unique_exact_matches(
    tmp_path: Path,
) -> None:
    """Strong source-name matches should be proposed once per audit field."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")
    invoice_column = column_by_source(dataset, "Invoice Number")

    suggestions = service.suggest_mappings(
        dataset,
        minimum_score=0.99,
    )

    assert suggestions[transaction_column.column_id] == "transaction_date"
    assert suggestions[account_column.column_id] == "account_code"
    assert suggestions[invoice_column.column_id] == "invoice_number"

    assert dataset.field_mappings[transaction_column.column_id] == "transaction_date"
    assert dataset.field_mappings[account_column.column_id] == "account_code"
    assert dataset.field_mappings[invoice_column.column_id] == "invoice_number"

    assert len(dataset.field_mappings.values()) == len(
        set(dataset.field_mappings.values())
    )
    assert dataset.mapping_status == FieldMappingStatus.IN_PROGRESS


def test_suggest_mappings_preserves_existing_mapping_and_does_not_reuse_field(
    tmp_path: Path,
) -> None:
    """Suggestions must preserve manual mappings and not reuse their audit fields."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )

    account_column.confirmed_name = "Transaction Date"

    suggestions = service.suggest_mappings(
        dataset,
        minimum_score=0.99,
    )

    assert dataset.field_mappings[transaction_column.column_id] == "transaction_date"
    assert suggestions.get(account_column.column_id) != "transaction_date"
    assert list(dataset.field_mappings.values()).count("transaction_date") == 1


def test_suggest_mappings_respects_minimum_score(
    tmp_path: Path,
) -> None:
    """Suggestions below the configured confidence threshold should be ignored."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    suggestions = service.suggest_mappings(
        dataset,
        minimum_score=1.01,
    )

    assert suggestions == {}
    assert dataset.field_mappings == {}
    assert dataset.mapping_status == FieldMappingStatus.NOT_STARTED


def test_match_score_normalises_case_punctuation_and_aliases(
    tmp_path: Path,
) -> None:
    """Matching should tolerate formatting differences and registered aliases."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_field = next(
        field
        for field in service.available_fields(dataset)
        if field.key == "transaction_date"
    )
    account_field = next(
        field
        for field in service.available_fields(dataset)
        if field.key == "account_code"
    )

    assert service.match_score(
        "TRANSACTION-DATE",
        transaction_field,
    ) == 1.0

    assert service.match_score(
        "GL CODE",
        account_field,
    ) == 1.0


def test_blank_assignment_removes_existing_mapping(
    tmp_path: Path,
) -> None:
    """Assigning a blank audit-field key should clear the mapping."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "   ",
    )

    assert transaction_column.column_id not in dataset.field_mappings
    assert dataset.mapping_status == FieldMappingStatus.NOT_STARTED


def test_removing_one_mapping_keeps_remaining_mapping_in_progress(
    tmp_path: Path,
) -> None:
    """Removing one mapping should not reset a dataset that still has mappings."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )
    service.assign_mapping(
        dataset,
        account_column.column_id,
        "account_code",
    )

    service.remove_mapping(
        dataset,
        transaction_column.column_id,
    )

    assert transaction_column.column_id not in dataset.field_mappings
    assert dataset.field_mappings[account_column.column_id] == "account_code"
    assert dataset.mapping_status == FieldMappingStatus.IN_PROGRESS


def test_confirmation_removes_mapping_for_column_no_longer_included(
    tmp_path: Path,
) -> None:
    """Confirmation should discard stale mappings to excluded prepared columns."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )
    service.assign_mapping(
        dataset,
        account_column.column_id,
        "account_code",
    )

    transaction_column.included = False

    status = service.confirm_dataset(dataset)

    assert status == FieldMappingStatus.CONFIRMED
    assert transaction_column.column_id not in dataset.field_mappings
    assert dataset.field_mappings[account_column.column_id] == "account_code"


def test_mapped_field_resolves_catalogue_field_and_unmapped_returns_none(
    tmp_path: Path,
) -> None:
    """Mapped columns should resolve to their catalogue definition."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    transaction_column = column_by_source(dataset, "Transaction Date")
    account_column = column_by_source(dataset, "Account Code")

    service.assign_mapping(
        dataset,
        transaction_column.column_id,
        "transaction_date",
    )

    mapped = service.mapped_field(
        dataset,
        transaction_column.column_id,
    )

    assert mapped is not None
    assert mapped.key == "transaction_date"

    assert (
        service.mapped_field(
            dataset,
            account_column.column_id,
        )
        is None
    )


def test_unknown_column_id_cannot_be_mapped(
    tmp_path: Path,
) -> None:
    """A stale or nonexistent prepared-column identifier must be rejected."""
    dataset = create_general_ledger_dataset(tmp_path)
    service = FieldMappingService()

    with pytest.raises(
        FieldMappingError,
        match="not available",
    ):
        service.assign_mapping(
            dataset,
            "missing-column-id",
            "transaction_date",
        )
