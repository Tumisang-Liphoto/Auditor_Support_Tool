"""Tests for audit workspace persistence."""

import json
from pathlib import Path

import pytest

from auditor_support_tool.core.constants import APP_VERSION
from auditor_support_tool.core.paths import ApplicationPaths
from auditor_support_tool.core.workspace_models import (
    WORKSPACE_FILE_EXTENSION,
    WorkspaceDocument,
    WorkspaceIdentity,
)
from auditor_support_tool.core.workspace_service import (
    UnsupportedWorkspaceVersionError,
    WorkspaceService,
    WorkspaceServiceError,
)
from auditor_support_tool.core.workspace_state import WorkspaceState


@pytest.fixture
def application_paths(tmp_path: Path) -> ApplicationPaths:
    """Return isolated application paths for workspace tests."""

    return ApplicationPaths(
        data=tmp_path / "data",
        config=tmp_path / "config",
        cache=tmp_path / "cache",
        logs=tmp_path / "logs",
        workspaces=tmp_path / "data" / "Workspaces",
        workspace_backups=(tmp_path / "data" / "Backups" / "Workspaces"),
        workspace_recovery=tmp_path / "data" / "Recovery",
        backups=tmp_path / "data" / "Backups" / "Application",
        updates=tmp_path / "cache" / "Updates",
        update_downloads=(tmp_path / "cache" / "Updates" / "Downloads"),
        update_staging=(tmp_path / "cache" / "Updates" / "Staging"),
        update_runtime=(tmp_path / "cache" / "Updates" / "Runtime"),
        temporary=tmp_path / "cache" / "Temporary",
    )


@pytest.fixture
def workspace_service(
    application_paths: ApplicationPaths,
) -> WorkspaceService:
    """Return an isolated workspace service."""

    return WorkspaceService(application_paths)


def test_save_document_adds_workspace_extension(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Workspace files receive the standard extension."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(name="Payroll Audit"),
        application_version=APP_VERSION,
    )

    saved_path = workspace_service.save_document(
        document=document,
        file_path=tmp_path / "payroll-audit",
    )

    assert saved_path.suffix == WORKSPACE_FILE_EXTENSION
    assert saved_path.is_file()


def test_save_and_load_document_round_trip(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """A saved workspace can be loaded without losing identity."""

    identity = WorkspaceIdentity.create(
        name="General Ledger Audit",
        auditee_name="Example Organisation",
        audit_year="2026",
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
    )

    document = WorkspaceDocument.create(
        identity=identity,
        application_version=APP_VERSION,
    )
    document.active_dataset_id = "dataset-001"
    document.field_mappings = {
        "dataset-001": {
            "transaction_date": "Posting Date",
        }
    }

    workspace_path = workspace_service.save_document(
        document=document,
        file_path=tmp_path / "general-ledger.astworkspace",
    )

    loaded = workspace_service.load_document(workspace_path)

    assert loaded.identity.workspace_id == identity.workspace_id
    assert loaded.identity.name == "General Ledger Audit"
    assert loaded.identity.auditee_name == "Example Organisation"
    assert loaded.identity.audit_year == "2026"
    assert loaded.identity.audit_period_start == "2026-04-01"
    assert loaded.identity.audit_period_end == "2027-03-31"
    assert loaded.identity.has_audit_period is True
    assert loaded.active_dataset_id == "dataset-001"
    assert loaded.field_mappings == document.field_mappings


def test_legacy_workspace_without_audit_period_loads(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Older workspace files without audit-period fields remain readable."""

    identity = WorkspaceIdentity.create(
        name="Legacy General Ledger Audit",
        auditee_name="Example Organisation",
        audit_year="2026",
    )

    raw_document = {
        "format_version": 1,
        "application_version": "0.1.2",
        "identity": {
            "workspace_id": identity.workspace_id,
            "name": identity.name,
            "auditee_name": identity.auditee_name,
            "audit_year": identity.audit_year,
            "audit_domain": "",
            "audit_area": "",
            "lead_auditor": "",
            "description": "",
            "created_at": identity.created_at,
            "modified_at": identity.modified_at,
        },
        "active_dataset_id": None,
        "source": None,
        "workbook_package": None,
        "field_mappings": {},
        "transformation_history": [],
        "data_quality_issues": [],
    }

    workspace_path = tmp_path / "legacy.astworkspace"
    workspace_path.write_text(
        json.dumps(raw_document),
        encoding="utf-8",
    )

    loaded = workspace_service.load_document(workspace_path)

    assert loaded.identity.name == "Legacy General Ledger Audit"
    assert loaded.identity.audit_year == "2026"
    assert loaded.identity.audit_period_start == ""
    assert loaded.identity.audit_period_end == ""
    assert loaded.identity.has_audit_period is False


def test_saved_workspace_contains_audit_period(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Audit-period dates should be written to workspace JSON."""

    identity = WorkspaceIdentity.create(
        name="Financial Audit",
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
    )

    document = WorkspaceDocument.create(
        identity=identity,
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document=document,
        file_path=tmp_path / "financial-audit.astworkspace",
    )

    raw_document = json.loads(workspace_path.read_text(encoding="utf-8"))

    raw_identity = raw_document["identity"]

    assert raw_identity["audit_period_start"] == "2026-04-01"
    assert raw_identity["audit_period_end"] == "2027-03-31"


def test_invalid_saved_audit_period_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Invalid audit-period metadata must not be loaded silently."""

    identity = WorkspaceIdentity.create(name="Invalid Period Audit")

    raw_document = {
        "format_version": 1,
        "application_version": APP_VERSION,
        "identity": {
            "workspace_id": identity.workspace_id,
            "name": identity.name,
            "auditee_name": "",
            "audit_year": "2026",
            "audit_period_start": "2027-03-31",
            "audit_period_end": "2026-04-01",
            "audit_domain": "",
            "audit_area": "",
            "lead_auditor": "",
            "description": "",
            "created_at": identity.created_at,
            "modified_at": identity.modified_at,
        },
        "active_dataset_id": None,
        "source": None,
        "workbook_package": None,
        "field_mappings": {},
        "transformation_history": [],
        "data_quality_issues": [],
    }

    workspace_path = tmp_path / "invalid-period.astworkspace"
    workspace_path.write_text(
        json.dumps(raw_document),
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match="Invalid audit period",
    ):
        workspace_service.load_document(workspace_path)


def test_save_state_requires_active_workspace(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Workspace state without an identity cannot be saved."""

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="No active audit workspace",
    ):
        workspace_service.save_state(
            state,
            tmp_path / "missing.astworkspace",
        )


def test_save_state_marks_workspace_clean(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Successful saving records the path and clears dirty state."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="Payroll Audit")

    state.start_workspace(identity)

    saved_path = workspace_service.save_state(
        state,
        tmp_path / "payroll.astworkspace",
    )

    assert saved_path.is_file()
    assert state.workspace_file_path == saved_path
    assert state.is_dirty is False


def test_load_into_state_starts_clean_workspace(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """A loaded workspace becomes the clean active workspace."""

    identity = WorkspaceIdentity.create(
        name="Payroll Audit",
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
    )
    document = WorkspaceDocument.create(
        identity=identity,
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document=document,
        file_path=tmp_path / "payroll.astworkspace",
    )

    state = WorkspaceState()

    loaded = workspace_service.load_into_state(
        state,
        workspace_path,
    )

    assert loaded.identity.name == "Payroll Audit"
    assert state.has_workspace is True
    assert state.workspace_identity is not None
    assert state.workspace_identity.workspace_id == identity.workspace_id
    assert state.workspace_identity.audit_period_start == "2026-04-01"
    assert state.workspace_identity.audit_period_end == "2027-03-31"
    assert state.workspace_file_path == workspace_path
    assert state.is_dirty is False


def test_overwrite_creates_backup(
    workspace_service: WorkspaceService,
    application_paths: ApplicationPaths,
    tmp_path: Path,
) -> None:
    """Overwriting an existing workspace preserves its prior version."""

    identity = WorkspaceIdentity.create(name="Payroll Audit")
    document = WorkspaceDocument.create(
        identity=identity,
        application_version=APP_VERSION,
    )
    workspace_path = tmp_path / "payroll.astworkspace"

    workspace_service.save_document(
        document,
        workspace_path,
    )

    document.identity.description = "Updated description"
    workspace_service.save_document(
        document,
        workspace_path,
    )

    backup_directory = application_paths.workspace_backups / workspace_path.stem
    backups = list(backup_directory.glob(f"*{WORKSPACE_FILE_EXTENSION}"))

    assert len(backups) == 1
    assert backups[0].is_file()


def test_invalid_json_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Malformed workspace files cannot be loaded."""

    workspace_path = tmp_path / "invalid.astworkspace"
    workspace_path.write_text(
        "{not valid json",
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match="does not contain valid JSON",
    ):
        workspace_service.load_document(workspace_path)


def test_unsupported_format_version_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Future unsupported formats cannot be loaded silently."""

    identity = WorkspaceIdentity.create(name="Future Workspace")

    raw_document = {
        "format_version": 999,
        "application_version": APP_VERSION,
        "identity": {
            "workspace_id": identity.workspace_id,
            "name": identity.name,
            "auditee_name": "",
            "audit_year": "",
            "audit_period_start": "",
            "audit_period_end": "",
            "audit_domain": "",
            "audit_area": "",
            "lead_auditor": "",
            "description": "",
            "created_at": identity.created_at,
            "modified_at": identity.modified_at,
        },
        "active_dataset_id": None,
        "source": None,
        "workbook_package": None,
        "field_mappings": {},
        "transformation_history": [],
        "data_quality_issues": [],
    }

    workspace_path = tmp_path / "future.astworkspace"
    workspace_path.write_text(
        json.dumps(raw_document),
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedWorkspaceVersionError):
        workspace_service.load_document(workspace_path)


def test_missing_workspace_file_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """A clear error is raised when the selected file is absent."""

    with pytest.raises(
        WorkspaceServiceError,
        match="Workspace file not found",
    ):
        workspace_service.load_document(tmp_path / "missing.astworkspace")
