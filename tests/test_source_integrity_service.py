"""Tests for SHA-256 source-file integrity handling."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.source_integrity_service import (
    SourceIntegrityService,
    SourceIntegrityStatus,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_service import (
    WorkspaceService,
    WorkspaceSourceIntegrityError,
)
from auditor_support_tool.core.workspace_state import WorkspaceState


def create_paths(
    tmp_path: Path,
):
    """Create the minimum application paths required by WorkspaceService."""

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
    """Create a small source workbook."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"
    worksheet.append(
        [
            "Transaction Date",
            "Account Code",
            "Amount",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "1000",
            125.00,
        ]
    )

    source_path = tmp_path / "source.xlsx"
    workbook.save(source_path)

    return source_path


def create_workspace_state(
    tmp_path: Path,
) -> WorkspaceState:
    """Create an active workspace with a loaded workbook package."""

    source_path = create_source_workbook(tmp_path)
    package = WorkbookPackageService().build_package(source_path)

    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name="Integrity Test",
            auditee_name="Example Auditee",
            audit_year="2026",
        )
    )
    state.set_workbook_package(package)

    return state


def test_sha256_changes_when_file_changes(
    tmp_path: Path,
) -> None:
    """SHA-256 should detect a change to source-file contents."""

    source_path = tmp_path / "source.txt"
    source_path.write_text("original", encoding="utf-8")

    service = SourceIntegrityService()
    original_hash = service.sha256_file(source_path)

    source_path.write_text("changed", encoding="utf-8")
    changed_hash = service.sha256_file(source_path)

    assert len(original_hash) == 64
    assert len(changed_hash) == 64
    assert original_hash != changed_hash


def test_matching_hash_is_verified(
    tmp_path: Path,
) -> None:
    """An unchanged source should verify against its stored hash."""

    source_path = tmp_path / "source.txt"
    source_path.write_text("audit data", encoding="utf-8")

    service = SourceIntegrityService()
    expected_hash = service.sha256_file(source_path)

    result = service.verify(
        source_path,
        expected_hash,
    )

    assert result.status == SourceIntegrityStatus.VERIFIED
    assert result.is_verified
    assert result.actual_sha256 == expected_hash


def test_workspace_save_records_managed_source_hash(
    tmp_path: Path,
) -> None:
    """Saved workspaces should persist the managed source SHA-256."""

    state = create_workspace_state(tmp_path)
    paths = create_paths(tmp_path)
    service = WorkspaceService(paths)

    workspace_path = service.save_state(
        state,
        paths.workspaces / "audit.astworkspace",
    )

    document = json.loads(workspace_path.read_text(encoding="utf-8"))

    source_hash = document["source"]["sha256"]

    assert isinstance(source_hash, str)
    assert len(source_hash) == 64

    managed_source = paths.workspaces / "audit.astdata" / "source" / "source.xlsx"

    assert source_hash == SourceIntegrityService().sha256_file(managed_source)


def test_modified_managed_source_is_blocked_by_default(
    tmp_path: Path,
) -> None:
    """A changed managed source should not open silently."""

    state = create_workspace_state(tmp_path)
    paths = create_paths(tmp_path)
    service = WorkspaceService(paths)

    workspace_path = service.save_state(
        state,
        paths.workspaces / "audit.astworkspace",
    )

    managed_source = paths.workspaces / "audit.astdata" / "source" / "source.xlsx"

    managed_source.write_bytes(managed_source.read_bytes() + b"tampered")

    restored_state = WorkspaceState()

    with pytest.raises(WorkspaceSourceIntegrityError):
        service.load_into_state(
            restored_state,
            workspace_path,
        )

    assert not restored_state.has_workspace


def test_integrity_mismatch_can_be_explicitly_accepted(
    tmp_path: Path,
) -> None:
    """An authorised UI override may open a mismatched source explicitly."""

    state = create_workspace_state(tmp_path)
    paths = create_paths(tmp_path)
    service = WorkspaceService(paths)

    workspace_path = service.save_state(
        state,
        paths.workspaces / "audit.astworkspace",
    )

    managed_source = paths.workspaces / "audit.astdata" / "source" / "source.xlsx"

    # Change a cell while keeping the workbook structurally valid.
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"
    worksheet.append(
        [
            "Transaction Date",
            "Account Code",
            "Amount",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "1000",
            999.00,
        ]
    )
    workbook.save(managed_source)

    restored_state = WorkspaceState()

    service.load_into_state(
        restored_state,
        workspace_path,
        allow_source_integrity_mismatch=True,
    )

    assert restored_state.has_workspace
    assert restored_state.has_workbook_package
