"""Tests for persisted workbook datasets inside audit workspaces."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from auditor_support_tool.core.workbook_package import (
    FieldMappingStatus,
    PreparationStatus,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_service import WorkspaceService
from auditor_support_tool.core.workspace_state import WorkspaceState


def create_paths(
    tmp_path: Path,
):
    """Create the minimum application paths used by WorkspaceService."""

    workspaces = tmp_path / "Workspaces"
    backups = tmp_path / "Backups"

    workspaces.mkdir(parents=True)
    backups.mkdir(parents=True)

    return SimpleNamespace(
        workspaces=workspaces,
        workspace_backups=backups,
    )


def create_source_workbook(
    tmp_path: Path,
) -> Path:
    """Create a small workbook containing two audit datasets."""

    workbook = Workbook()

    general_ledger = workbook.active
    general_ledger.title = "General_Ledger"
    general_ledger.append(
        [
            "Transaction Date",
            "Account Code",
            "Amount",
            "Description",
        ]
    )
    general_ledger.append(
        [
            "2026-01-03",
            "1000",
            125.50,
            "Weekend payment",
        ]
    )
    general_ledger.append(
        [
            "2026-01-05",
            "2000",
            250.00,
            "Normal payment",
        ]
    )

    trial_balance = workbook.create_sheet("Trial_Balance")
    trial_balance.append(
        [
            "Account Code",
            "Debit",
            "Credit",
        ]
    )
    trial_balance.append(
        [
            "1000",
            125.50,
            0.00,
        ]
    )

    source_path = tmp_path / "audit_source.xlsx"
    workbook.save(source_path)

    return source_path


def prepare_workspace(
    tmp_path: Path,
) -> tuple[
    WorkspaceState,
    str,
    str,
    str,
]:
    """Create a workspace containing prepared and mapped workbook data."""

    source_path = create_source_workbook(tmp_path)
    package = WorkbookPackageService().build_package(source_path)

    general_ledger = package.get_dataset_by_worksheet("General_Ledger")
    trial_balance = package.get_dataset_by_worksheet("Trial_Balance")

    assert general_ledger is not None
    assert trial_balance is not None

    general_ledger.status = PreparationStatus.CONFIRMED
    general_ledger.preparation_status = PreparationStatus.CONFIRMED
    general_ledger.mapping_status = FieldMappingStatus.CONFIRMED
    general_ledger.confirmed_display_name = "General Ledger 2026"

    transaction_column = next(
        column for column in general_ledger.columns if column.source_column == "Transaction Date"
    )
    transaction_column.confirmed_name = "Posting Date"

    description_column = next(
        column for column in general_ledger.columns if column.source_column == "Description"
    )
    description_column.included = False
    description_column.status = PreparationStatus.EXCLUDED

    general_ledger.field_mappings[transaction_column.column_id] = "transaction_date"

    trial_balance.status = PreparationStatus.CONFIRMED

    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name="Dataset Persistence Test",
            auditee_name="Example Auditee",
            audit_year="2026",
        )
    )
    state.set_workbook_package(package)
    state.set_active_dataset(trial_balance.dataset_id)

    return (
        state,
        general_ledger.dataset_id,
        transaction_column.column_id,
        trial_balance.dataset_id,
    )


def test_snapshot_restore_preserves_stable_ids_and_decisions(
    tmp_path: Path,
) -> None:
    """Workbook snapshots should restore IDs, preparation and mappings."""

    source_path = create_source_workbook(tmp_path)
    service = WorkbookPackageService()
    package = service.build_package(source_path)

    dataset = package.get_dataset_by_worksheet("General_Ledger")
    assert dataset is not None

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.CONFIRMED
    dataset.mapping_status = FieldMappingStatus.CONFIRMED
    dataset.confirmed_display_name = "Prepared General Ledger"

    column = next(
        prepared_column
        for prepared_column in dataset.columns
        if prepared_column.source_column == "Transaction Date"
    )
    column.confirmed_name = "Posting Date"
    dataset.field_mappings[column.column_id] = "transaction_date"

    expected_dataset_id = dataset.dataset_id
    expected_column_id = column.column_id

    snapshot = service.snapshot_package(package)
    restored = service.restore_package(
        source_path,
        snapshot,
    )

    restored_dataset = restored.get_dataset(expected_dataset_id)
    assert restored_dataset is not None
    assert restored_dataset.confirmed_display_name == "Prepared General Ledger"
    assert restored_dataset.preparation_status == PreparationStatus.CONFIRMED
    assert restored_dataset.mapping_status == FieldMappingStatus.CONFIRMED

    restored_column = restored_dataset.get_column(expected_column_id)
    assert restored_column is not None
    assert restored_column.confirmed_name == "Posting Date"
    assert restored_dataset.field_mappings[expected_column_id] == "transaction_date"


def test_workspace_save_creates_managed_source_and_snapshot(
    tmp_path: Path,
) -> None:
    """Saving should preserve source data beside the workspace file."""

    state, _dataset_id, _column_id, _active_id = prepare_workspace(tmp_path)
    paths = create_paths(tmp_path)
    service = WorkspaceService(paths)

    workspace_path = service.save_state(
        state,
        paths.workspaces / "audit.astworkspace",
    )

    managed_source = paths.workspaces / "audit.astdata" / "source" / "audit_source.xlsx"

    assert workspace_path.is_file()
    assert managed_source.is_file()

    raw_document = json.loads(workspace_path.read_text(encoding="utf-8"))

    assert raw_document["workbook_package"] is not None
    assert not Path(raw_document["source"]["source_path"]).is_absolute()
    assert raw_document["workbook_package"]["datasets"]


def test_workspace_reopens_without_original_excel_file(
    tmp_path: Path,
) -> None:
    """The managed source copy should allow a workspace to reopen alone."""

    (
        state,
        expected_dataset_id,
        expected_column_id,
        expected_active_id,
    ) = prepare_workspace(tmp_path)

    original_source = state.source_path
    assert original_source is not None

    paths = create_paths(tmp_path)
    service = WorkspaceService(paths)

    workspace_path = service.save_state(
        state,
        paths.workspaces / "audit.astworkspace",
    )

    original_source.unlink()
    assert not original_source.exists()

    restored_state = WorkspaceState()
    service.load_into_state(
        restored_state,
        workspace_path,
    )

    assert restored_state.has_workbook_package
    assert restored_state.source_path is not None
    assert restored_state.source_path.is_file()
    assert restored_state.active_dataset_id == expected_active_id

    restored_dataset = restored_state.workbook_package.get_dataset(expected_dataset_id)
    assert restored_dataset is not None
    assert restored_dataset.record_count == 2
    assert restored_dataset.confirmed_display_name == "General Ledger 2026"
    assert restored_dataset.preparation_status == PreparationStatus.CONFIRMED
    assert restored_dataset.mapping_status == FieldMappingStatus.CONFIRMED

    restored_column = restored_dataset.get_column(expected_column_id)
    assert restored_column is not None
    assert restored_column.confirmed_name == "Posting Date"
    assert restored_dataset.field_mappings[expected_column_id] == "transaction_date"

    description_column = next(
        column for column in restored_dataset.columns if column.source_column == "Description"
    )
    assert not description_column.included
    assert description_column.status == PreparationStatus.EXCLUDED
    assert not restored_state.is_dirty


def test_save_as_creates_independent_managed_source(
    tmp_path: Path,
) -> None:
    """Save As should create source data beside the new workspace file."""

    state, _dataset_id, _column_id, _active_id = prepare_workspace(tmp_path)
    paths = create_paths(tmp_path)
    service = WorkspaceService(paths)

    first_workspace = service.save_state(
        state,
        paths.workspaces / "first.astworkspace",
    )

    restored_state = WorkspaceState()
    service.load_into_state(
        restored_state,
        first_workspace,
    )

    second_workspace = service.save_state(
        restored_state,
        paths.workspaces / "second.astworkspace",
    )

    second_source = paths.workspaces / "second.astdata" / "source" / "audit_source.xlsx"

    assert second_workspace.is_file()
    assert second_source.is_file()
