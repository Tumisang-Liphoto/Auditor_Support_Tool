"""Tests for editable dataset preparation decisions."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.data_preparation_service import (
    DataPreparationError,
    DataPreparationService,
)
from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
    PreparedColumn,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)


def create_dataset(
    tmp_path: Path,
) -> WorksheetDataset:
    """Create a General Ledger dataset for preparation tests."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"

    worksheet.append(
        [
            "Account Code",
            "Transaction Date",
            "Amount",
            "Description",
        ]
    )
    worksheet.append(
        [
            1000,
            "2026-01-01",
            150.50,
            "Payment",
        ]
    )
    worksheet.append(
        [
            2000,
            "2026-01-02",
            75.00,
            "Receipt",
        ]
    )

    path = tmp_path / "preparation.xlsx"
    workbook.save(path)

    package = WorkbookPackageService().build_package(path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

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


def test_column_name_can_be_changed(
    tmp_path: Path,
) -> None:
    """A prepared column name should remain editable."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    account_column = column_by_source(dataset, "Account Code")

    column = service.update_column_name(
        dataset,
        account_column.column_id,
        "Account Number",
    )

    assert column.confirmed_name == "Account Number"
    assert dataset.preparation_status == PreparationStatus.NOT_REVIEWED


def test_blank_column_name_is_rejected(
    tmp_path: Path,
) -> None:
    """Included columns cannot have blank prepared names."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    account_column = column_by_source(dataset, "Account Code")

    with pytest.raises(
        DataPreparationError,
        match="cannot be blank",
    ):
        service.update_column_name(
            dataset,
            account_column.column_id,
            "   ",
        )


def test_duplicate_prepared_name_is_rejected(
    tmp_path: Path,
) -> None:
    """Included columns require unique prepared names."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    account_column = column_by_source(dataset, "Account Code")

    with pytest.raises(
        DataPreparationError,
        match="already used",
    ):
        service.update_column_name(
            dataset,
            account_column.column_id,
            "Amount",
        )


def test_identifier_can_be_confirmed_as_text(
    tmp_path: Path,
) -> None:
    """Numeric identifiers may safely be interpreted as text."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    account_column = column_by_source(dataset, "Account Code")

    column = service.update_column_type(
        dataset,
        account_column.column_id,
        DetectedDataType.TEXT,
    )

    assert column.confirmed_type == DetectedDataType.TEXT
    assert column.validation_warning == ""


def test_incompatible_type_change_creates_warning(
    tmp_path: Path,
) -> None:
    """A type override requiring conversion should be flagged."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    description_column = column_by_source(dataset, "Description")

    column = service.update_column_type(
        dataset,
        description_column.column_id,
        DetectedDataType.DATE,
    )

    assert column.validation_warning
    assert column.status == PreparationStatus.CONFIRMED_WITH_WARNINGS


def test_column_can_be_excluded(
    tmp_path: Path,
) -> None:
    """A prepared source column may be excluded from later stages."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    description_column = column_by_source(dataset, "Description")

    column = service.set_column_included(
        dataset,
        description_column.column_id,
        False,
    )

    assert not column.included
    assert column.status == PreparationStatus.EXCLUDED
    assert column not in dataset.included_columns


def test_confirm_dataset_without_warnings(
    tmp_path: Path,
) -> None:
    """A valid preparation should be confirmed."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    status = service.confirm_dataset(dataset)

    assert status == PreparationStatus.CONFIRMED
    assert all(column.status == PreparationStatus.CONFIRMED for column in dataset.included_columns)


def test_confirm_dataset_with_warning(
    tmp_path: Path,
) -> None:
    """A valid preparation may be confirmed with warnings."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()
    description_column = column_by_source(dataset, "Description")

    service.update_column_type(
        dataset,
        description_column.column_id,
        DetectedDataType.DATE,
    )

    status = service.confirm_dataset(dataset)

    assert status == PreparationStatus.CONFIRMED_WITH_WARNINGS


def test_dataset_requires_one_included_column(
    tmp_path: Path,
) -> None:
    """A selected dataset cannot contain zero included columns."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    for column in dataset.columns:
        service.set_column_included(
            dataset,
            column.column_id,
            False,
        )

    with pytest.raises(
        DataPreparationError,
        match="at least one included column",
    ):
        service.confirm_dataset(dataset)


def test_reset_restores_suggestions(
    tmp_path: Path,
) -> None:
    """Reset should restore suggested names and types."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    account_column = column_by_source(dataset, "Account Code")
    description_column = column_by_source(dataset, "Description")

    service.update_column_name(
        dataset,
        account_column.column_id,
        "Changed Name",
    )
    service.update_column_type(
        dataset,
        account_column.column_id,
        DetectedDataType.TEXT,
    )
    service.set_column_included(
        dataset,
        description_column.column_id,
        False,
    )

    service.reset_dataset(dataset)

    assert account_column.confirmed_name == account_column.suggested_name
    assert account_column.confirmed_type == account_column.suggested_type
    assert all(column.included for column in dataset.columns)
    assert dataset.preparation_status == PreparationStatus.NOT_REVIEWED


def test_unknown_column_is_rejected(
    tmp_path: Path,
) -> None:
    """Preparation changes require an existing stable column identifier."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    with pytest.raises(
        DataPreparationError,
        match="could not be found",
    ):
        service.set_column_included(
            dataset,
            "column-missing",
            False,
        )
