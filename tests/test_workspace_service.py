"""Tests for audit workspace persistence."""

import json
from pathlib import Path

import pytest

from auditor_support_tool.core.constants import APP_VERSION
from auditor_support_tool.core.paths import ApplicationPaths
from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
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

def _create_saved_source_workspace(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> Path:
    """Create a saved workspace containing a real managed source and dataset."""

    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "Code,Amount\nA001,100\n",
        encoding="utf-8",
    )

    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name="Source Workspace",
        )
    )
    state.set_workbook_package(
        WorkbookPackageService().build_package(source_path)
    )

    return workspace_service.save_state(
        state,
        tmp_path / "source-workspace.astworkspace",
    )


def test_first_save_requires_workspace_path(
    workspace_service: WorkspaceService,
) -> None:
    """The first save must not guess where an audit workspace belongs."""

    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name="Unsaved Audit",
        )
    )

    with pytest.raises(
        WorkspaceServiceError,
        match="workspace file path is required",
    ):
        workspace_service.save_state(state)


def test_json_array_is_rejected_as_workspace_document(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Valid JSON is insufficient when the workspace root is not an object."""

    workspace_path = tmp_path / "invalid-structure.astworkspace"
    workspace_path.write_text(
        json.dumps(["not", "a", "workspace"]),
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match="invalid top-level structure",
    ):
        workspace_service.load_document(workspace_path)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    (
        (
            "identity",
            [],
            "Workspace identity must be an object",
        ),
        (
            "source",
            [],
            "Workspace source must be an object",
        ),
        (
            "workbook_package",
            [],
            "Workbook package must be an object or null",
        ),
        (
            "field_mappings",
            [],
            "Field mappings must be an object",
        ),
        (
            "transformation_history",
            {},
            "Transformation history must be an array",
        ),
        (
            "transformation_history",
            [1],
            "Transformation history entries must be objects",
        ),
        (
            "data_quality_issues",
            {},
            "Data-quality issues must be an array",
        ),
        (
            "data_quality_issues",
            [1],
            "Data-quality issue entries must be objects",
        ),
        (
            "procedure_execution_stamps",
            {},
            "Procedure execution stamps must be an array",
        ),
        (
            "procedure_execution_stamps",
            [1],
            "Procedure execution stamp entries must be objects",
        ),
        (
            "procedure_parameters",
            [],
            "Procedure parameters must be an object",
        ),
    ),
)
def test_invalid_workspace_section_shapes_are_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
    field_name: str,
    invalid_value,
    message: str,
) -> None:
    """Malformed persisted workspace sections must fail closed."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Structure Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "structure.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload[field_name] = invalid_value

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match=message,
    ):
        workspace_service.load_document(workspace_path)


@pytest.mark.parametrize(
    ("parameters", "message"),
    (
        (
            {
                "": {
                    "threshold": "100",
                }
            },
            "procedure IDs cannot be blank",
        ),
        (
            {
                "GL003": [],
            },
            "parameter entry must be an object",
        ),
        (
            {
                "GL003": {
                    "": "100",
                }
            },
            "parameter keys cannot be blank",
        ),
    ),
)
def test_invalid_persisted_procedure_parameter_structure_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
    parameters,
    message: str,
) -> None:
    """Corrupted procedure settings must never reach procedure execution."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Parameter Structure Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "parameters.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["procedure_parameters"] = parameters

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match=message,
    ):
        workspace_service.load_document(workspace_path)


def test_dataset_snapshot_without_source_reference_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Dataset metadata must never be restored without its bound source."""

    workspace_path = _create_saved_source_workspace(
        workspace_service,
        tmp_path,
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["source"] = None

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="dataset metadata but no source-file reference",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


def test_missing_managed_source_blocks_workspace_restore(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """A workspace must not reopen when its committed source bytes are missing."""

    workspace_path = _create_saved_source_workspace(
        workspace_service,
        tmp_path,
    )

    document = workspace_service.load_document(
        workspace_path
    )

    assert document.source is not None

    managed_source = (
        workspace_service._resolve_workspace_source_path(
            document.source,
            workspace_path,
        )
    )
    managed_source.unlink()

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="managed source file could not be found",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


def test_source_integrity_verification_error_blocks_restore(
    workspace_service: WorkspaceService,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Integrity verification failures must stop state reconstruction."""

    workspace_path = _create_saved_source_workspace(
        workspace_service,
        tmp_path,
    )

    def fail_verification(*_args, **_kwargs):
        raise ValueError("invalid stored source fingerprint")

    monkeypatch.setattr(
        workspace_service._source_integrity_service,
        "verify",
        fail_verification,
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="Could not verify workspace source integrity",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


def test_dataset_restore_failure_blocks_workspace_restore(
    workspace_service: WorkspaceService,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Invalid saved dataset metadata must not create a partial workspace."""

    workspace_path = _create_saved_source_workspace(
        workspace_service,
        tmp_path,
    )

    def fail_restore(*_args, **_kwargs):
        raise ValueError("invalid dataset snapshot")

    monkeypatch.setattr(
        workspace_service._workbook_package_service,
        "restore_package",
        fail_restore,
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="Could not restore saved datasets",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


def test_missing_saved_active_dataset_blocks_restore(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """The saved active dataset must exist in the reconstructed package."""

    workspace_path = _create_saved_source_workspace(
        workspace_service,
        tmp_path,
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["active_dataset_id"] = "missing-dataset-id"

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="saved active dataset could not be restored",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


@pytest.mark.parametrize(
    ("field_name", "message"),
    (
        (
            "transformation_history",
            "Invalid transformation-history entry",
        ),
        (
            "data_quality_issues",
            "Invalid data-quality issue entry",
        ),
    ),
)
def test_invalid_saved_audit_history_blocks_workspace_restore(
    workspace_service: WorkspaceService,
    tmp_path: Path,
    field_name: str,
    message: str,
) -> None:
    """Corrupted audit-history metadata must not produce a partial workspace."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Audit History Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "history.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload[field_name] = [{}]

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match=message,
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace

def test_invalid_procedure_execution_stamp_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Corrupted saved execution evidence must not be accepted."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Execution Stamp Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "execution-stamp.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["procedure_execution_stamps"] = [
        {
            "execution_id": "incomplete",
        }
    ]

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match="Invalid procedure execution stamp",
    ):
        workspace_service.load_document(workspace_path)


def test_valid_transformation_history_is_restored(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Persisted transformation evidence should reconstruct deterministically."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Transformation Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "transformation.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["transformation_history"] = [
        {
            "record_id": "transform-001",
            "timestamp": "2026-09-13T08:00:00+00:00",
            "action": "confirm_mapping",
            "dataset_id": "dataset-001",
            "column_id": "column-001",
            "source_column": "Invoice Number",
            "old_value": None,
            "new_value": "invoice_number",
            "details": {
                "reviewer": "Auditor",
            },
        }
    ]

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = WorkspaceState()

    workspace_service.load_into_state(
        state,
        workspace_path,
    )

    assert len(state.transformation_history) == 1

    record = state.transformation_history[0]

    assert record.record_id == "transform-001"
    assert record.action == "confirm_mapping"
    assert record.dataset_id == "dataset-001"
    assert record.column_id == "column-001"
    assert record.source_column == "Invoice Number"
    assert record.old_value is None
    assert record.new_value == "invoice_number"
    assert record.details == {
        "reviewer": "Auditor",
    }
    assert state.is_dirty is False


def test_invalid_transformation_details_are_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Transformation metadata must retain its structured audit-trail form."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Transformation Validation Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "invalid-transformation.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["transformation_history"] = [
        {
            "record_id": "transform-001",
            "timestamp": "2026-09-13T08:00:00+00:00",
            "action": "confirm_mapping",
            "details": [
                "not",
                "an",
                "object",
            ],
        }
    ]

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="Transformation details must be an object",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


def test_blank_data_quality_issue_identifier_is_rejected(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Corrupted data-quality evidence must prevent workspace reconstruction."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Data Quality Validation Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "invalid-data-quality.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )
    payload["data_quality_issues"] = [
        {
            "issue_id": "   ",
            "detected_at": "2026-09-13T08:00:00+00:00",
            "code": "TEST_ISSUE",
            "message": "Test data-quality issue.",
            "dataset_id": "dataset-001",
        }
    ]

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    state = WorkspaceState()

    with pytest.raises(
        WorkspaceServiceError,
        match="Data-quality issue identifier is required",
    ):
        workspace_service.load_into_state(
            state,
            workspace_path,
        )

    assert not state.has_workspace


@pytest.mark.parametrize(
    ("field_path", "message"),
    (
        (
            ("application_version",),
            "Workspace application version is required",
        ),
        (
            ("identity", "workspace_id"),
            "Workspace identifier is required",
        ),
        (
            ("identity", "name"),
            "Workspace name is required",
        ),
        (
            ("identity", "created_at"),
            "Workspace creation date is required",
        ),
        (
            ("identity", "modified_at"),
            "Workspace modification date is required",
        ),
    ),
)
def test_required_workspace_metadata_cannot_be_blank(
    workspace_service: WorkspaceService,
    tmp_path: Path,
    field_path: tuple[str, ...],
    message: str,
) -> None:
    """Core workspace identity fields must fail closed when corrupted."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Metadata Validation Test",
        ),
        application_version=APP_VERSION,
    )

    workspace_path = workspace_service.save_document(
        document,
        tmp_path / "metadata.astworkspace",
    )

    payload = json.loads(
        workspace_path.read_text(
            encoding="utf-8",
        )
    )

    target = payload

    for key in field_path[:-1]:
        target = target[key]

    target[field_path[-1]] = "   "

    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    with pytest.raises(
        WorkspaceServiceError,
        match=message,
    ):
        workspace_service.load_document(workspace_path)


def test_rerun_requirement_survives_workspace_save_and_reopen(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """A failed latest attempt must remain Needs Re-run after reopening."""

    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name="Execution State Persistence",
        )
    )

    stamp = ProcedureExecutionStamp.create(
        execution_id="successful-run-001",
        procedure_id="GL001",
        procedure_version="1.0",
        dataset_id="dataset-1",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        completed_at="2026-09-13T08:00:00+00:00",
    )

    state.record_procedure_execution(stamp)
    state.mark_procedure_rerun_required(
        "GL001",
        "dataset-1",
    )

    saved_path = workspace_service.save_state(
        state,
        tmp_path / "rerun-state.astworkspace",
    )

    reopened = WorkspaceState()
    workspace_service.load_into_state(
        reopened,
        saved_path,
    )

    assert (
        reopened.get_procedure_execution_stamp(
            "GL001",
            "dataset-1",
        )
        == stamp
    )
    assert reopened.procedure_requires_rerun(
        "GL001",
        "dataset-1",
    )
    assert reopened.is_dirty is False


def test_rerun_requirement_requires_successful_execution(
    workspace_service: WorkspaceService,
    tmp_path: Path,
) -> None:
    """Persisted rerun state must never exist without successful evidence."""

    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(
            name="Invalid Rerun State",
        ),
        application_version=APP_VERSION,
    )
    document.procedure_rerun_requirements = [
        {
            "procedure_id": "GL001",
            "dataset_id": "dataset-1",
        }
    ]

    with pytest.raises(
        WorkspaceServiceError,
        match="must reference a successful procedure execution",
    ):
        workspace_service.save_document(
            document,
            tmp_path / "invalid-rerun.astworkspace",
        )

