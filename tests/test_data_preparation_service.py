"""Tests for editable dataset preparation decisions."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.data_preparation_service import (
    DataPreparationError,
    DataPreparationService,
)
from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DetectedDataType,
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


def test_column_name_can_be_changed(
    tmp_path: Path,
) -> None:
    """A prepared column name should remain editable."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    column = service.update_column_name(
        dataset,
        "Account Code",
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

    with pytest.raises(
        DataPreparationError,
        match="cannot be blank",
    ):
        service.update_column_name(
            dataset,
            "Account Code",
            "   ",
        )


def test_duplicate_prepared_name_is_rejected(
    tmp_path: Path,
) -> None:
    """Included columns require unique prepared names."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    with pytest.raises(
        DataPreparationError,
        match="already used",
    ):
        service.update_column_name(
            dataset,
            "Account Code",
            "Amount",
        )


def test_identifier_can_be_confirmed_as_text(
    tmp_path: Path,
) -> None:
    """Numeric identifiers may safely be interpreted as text."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    column = service.update_column_type(
        dataset,
        "Account Code",
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

    column = service.update_column_type(
        dataset,
        "Description",
        DetectedDataType.DATE,
    )

    assert column.validation_warning
    assert column.status == PreparationStatus.CONFIRMED_WITH_WARNINGS


def test_column_can_be_excluded(
    tmp_path: Path,
) -> None:
    """A source column may be excluded from later stages."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    column = service.set_column_included(
        dataset,
        "Description",
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

    service.update_column_type(
        dataset,
        "Description",
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
            column.source_column,
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

    account_column = next(
        column for column in dataset.columns if column.source_column == "Account Code"
    )

    service.update_column_name(
        dataset,
        "Account Code",
        "Changed Name",
    )
    service.update_column_type(
        dataset,
        "Account Code",
        DetectedDataType.TEXT,
    )
    service.set_column_included(
        dataset,
        "Description",
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
    """Preparation changes require an existing source column."""

    dataset = create_dataset(tmp_path)
    service = DataPreparationService()

    with pytest.raises(
        DataPreparationError,
        match="Unknown source column",
    ):
        service.set_column_included(
            dataset,
            "Missing Column",
            False,
        )
