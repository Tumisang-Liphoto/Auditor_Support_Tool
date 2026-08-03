"""Tests for the shared multi-worksheet workspace state."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.core.workspace_state import WorkspaceState


def create_workspace_package(tmp_path: Path):
    """Create a workbook package containing two worksheets."""

    workbook = Workbook()

    ledger = workbook.active
    ledger.title = "General_Ledger"
    ledger.append(
        [
            "Transaction Date",
            "Account Code",
            "Amount",
        ]
    )
    ledger.append(
        [
            "2026-01-01",
            "1000",
            100.00,
        ]
    )

    chart = workbook.create_sheet("Chart_of_Accounts")
    chart.append(
        [
            "Account Code",
            "Account Name",
        ]
    )
    chart.append(
        [
            "1000",
            "Cash",
        ]
    )

    path = tmp_path / "workspace_data.xlsx"
    workbook.save(path)

    return WorkbookPackageService().build_package(path)


def test_setting_package_selects_first_dataset(
    tmp_path: Path,
) -> None:
    """The first selected worksheet should become active."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()

    state.set_workbook_package(package)

    assert state.has_workbook_package
    assert state.has_active_dataset
    assert state.active_dataset is not None
    assert state.active_dataset.original_worksheet_name == "General_Ledger"


def test_package_exposes_all_datasets(
    tmp_path: Path,
) -> None:
    """The workspace should retain all loaded worksheets."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()

    state.set_workbook_package(package)

    assert len(state.datasets) == 2
    assert tuple(dataset.original_worksheet_name for dataset in state.datasets) == (
        "General_Ledger",
        "Chart_of_Accounts",
    )


def test_active_dataset_can_be_changed(
    tmp_path: Path,
) -> None:
    """A different worksheet should be selectable for review."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()
    state.set_workbook_package(package)

    chart = package.get_dataset_by_worksheet("Chart_of_Accounts")

    assert chart is not None

    state.set_active_dataset(chart.dataset_id)

    assert state.active_dataset is chart
    assert state.selected_worksheet == "Chart_of_Accounts"
    assert state.loaded_table is chart.loaded_table
    assert state.data_profile is chart.data_profile


def test_dataset_can_be_excluded(
    tmp_path: Path,
) -> None:
    """Worksheets should be includable or excludable."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()
    state.set_workbook_package(package)

    chart = package.get_dataset_by_worksheet("Chart_of_Accounts")

    assert chart is not None

    state.set_dataset_selected(
        chart.dataset_id,
        False,
    )

    assert not chart.selected
    assert chart not in state.selected_datasets


def test_unknown_dataset_is_rejected(
    tmp_path: Path,
) -> None:
    """An unknown dataset identifier should raise an error."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()
    state.set_workbook_package(package)

    with pytest.raises(
        ValueError,
        match="Unknown dataset identifier",
    ):
        state.set_active_dataset("missing-dataset")


def test_active_dataset_requires_package() -> None:
    """A dataset cannot be selected without a package."""

    state = WorkspaceState()

    with pytest.raises(
        ValueError,
        match="No workbook package",
    ):
        state.set_active_dataset("dataset-0001")


def test_clear_removes_complete_package(
    tmp_path: Path,
) -> None:
    """Clearing should remove all workbook and dataset state."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()
    state.set_workbook_package(package)

    state.clear()

    assert state.workbook_package is None
    assert state.active_dataset is None
    assert state.datasets == ()
    assert state.loaded_table is None
    assert state.data_profile is None
    assert not state.has_source


def test_preparation_status_is_separate_from_navigator_status(
    tmp_path: Path,
) -> None:
    """Preparation changes must not remove Navigator confirmation."""

    package = create_workspace_package(tmp_path)
    state = WorkspaceState()
    state.set_workbook_package(package)

    dataset = package.datasets[0]

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.NOT_REVIEWED

    assert dataset.status == PreparationStatus.CONFIRMED
    assert dataset.preparation_status == PreparationStatus.NOT_REVIEWED
