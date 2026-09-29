"""Tests for local workspace autosave recovery persistence."""

from dataclasses import replace
from pathlib import Path

import pytest

from auditor_support_tool.core.data_models import SourceFileInfo
from auditor_support_tool.core.paths import ApplicationPaths
from auditor_support_tool.core.source_integrity_service import SourceIntegrityService
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_recovery_service import (
    WorkspaceRecoveryError,
    WorkspaceRecoveryService,
)
from auditor_support_tool.core.workspace_service import WorkspaceService
from auditor_support_tool.core.workspace_state import WorkspaceState


@pytest.fixture
def application_paths(tmp_path: Path) -> ApplicationPaths:
    """Return isolated paths including the application recovery folder."""

    return ApplicationPaths(
        data=tmp_path / "data",
        config=tmp_path / "config",
        cache=tmp_path / "cache",
        logs=tmp_path / "logs",
        workspaces=tmp_path / "data" / "Workspaces",
        workspace_backups=tmp_path / "data" / "Backups" / "Workspaces",
        workspace_recovery=tmp_path / "data" / "Recovery",
        backups=tmp_path / "data" / "Backups" / "Application",
        updates=tmp_path / "cache" / "Updates",
        update_downloads=tmp_path / "cache" / "Updates" / "Downloads",
        update_staging=tmp_path / "cache" / "Updates" / "Staging",
        update_runtime=tmp_path / "cache" / "Updates" / "Runtime",
        temporary=tmp_path / "cache" / "Temporary",
    )


@pytest.fixture
def recovery_service(
    application_paths: ApplicationPaths,
) -> WorkspaceRecoveryService:
    """Return a recovery service using the normal workspace serializer."""

    workspace_service = WorkspaceService(application_paths)
    return WorkspaceRecoveryService(application_paths, workspace_service)


def _dirty_workspace(name: str = "Unsaved audit") -> WorkspaceState:
    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name=name,
            auditee_name="Example Organisation",
            audit_year="2026",
        )
    )
    state.set_procedure_parameters("GL003", {"include_public_holidays": True})
    return state


def test_recovery_uses_workspace_schema_without_marking_state_saved(
    recovery_service: WorkspaceRecoveryService,
) -> None:
    state = _dirty_workspace()

    snapshot = recovery_service.save(state)
    discovered = recovery_service.discover()

    assert snapshot.path == recovery_service.recovery_path
    assert discovered is not None
    assert discovered.document == snapshot.document
    assert discovered.document.identity.name == "Unsaved audit"
    assert discovered.document.procedure_parameters == {"GL003": {"include_public_holidays": True}}
    assert state.is_dirty
    assert state.workspace_file_path is None
    assert not snapshot.path.with_suffix(f"{snapshot.path.suffix}.bak").exists()


def test_recovery_does_not_copy_source_data(
    recovery_service: WorkspaceRecoveryService,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    source.write_text("entry,amount\n1,10\n", encoding="utf-8")
    state = _dirty_workspace()
    package = WorkbookPackageService().build_package(source)
    state.set_workbook_package(package)

    snapshot = recovery_service.save(state)

    assert snapshot.document.source is not None
    assert snapshot.document.source.source_path == str(source)
    assert snapshot.document.source.sha256 == package.datasets[0].loaded_table.source_sha256
    assert sorted(path.name for path in snapshot.path.parent.iterdir()) == [snapshot.path.name]


def test_recovery_reuses_loaded_hash_without_rehashing_source(
    recovery_service: WorkspaceRecoveryService,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "large-source.csv"
    source.write_text("entry,amount\n1,10\n", encoding="utf-8")
    state = _dirty_workspace()
    package = WorkbookPackageService().build_package(source)
    state.set_workbook_package(package)
    loaded_hash = package.datasets[0].loaded_table.source_sha256
    monkeypatch.setattr(
        SourceIntegrityService,
        "sha256_file",
        lambda *_args, **_kwargs: pytest.fail("autosave must not rehash source bytes"),
    )

    snapshot = recovery_service.save(state)

    assert snapshot.document.source is not None
    assert snapshot.document.source.sha256 == loaded_hash


def test_recovery_fails_without_a_trustworthy_loaded_source_hash(
    recovery_service: WorkspaceRecoveryService,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.csv"
    source.write_text("entry,amount\n1,10\n", encoding="utf-8")
    state = _dirty_workspace()
    state.set_source(
        SourceFileInfo(
            path=source,
            file_type="csv",
            file_size_bytes=source.stat().st_size,
            worksheets=(),
        )
    )

    with pytest.raises(WorkspaceRecoveryError, match="fingerprint is unavailable"):
        recovery_service.save(state)

    assert not recovery_service.recovery_path.exists()


def test_failed_atomic_replacement_preserves_last_valid_recovery(
    recovery_service: WorkspaceRecoveryService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _dirty_workspace("First version")
    recovery_service.save(state)
    previous_bytes = recovery_service.recovery_path.read_bytes()
    state.update_workspace_identity(replace(state.workspace_identity, name="Second version"))
    original_replace = Path.replace

    def fail_recovery_replace(path: Path, target: Path) -> Path:
        if target == recovery_service.recovery_path:
            raise OSError("simulated interrupted replacement")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_recovery_replace)

    with pytest.raises(WorkspaceRecoveryError, match="Could not autosave"):
        recovery_service.save(state)

    assert recovery_service.recovery_path.read_bytes() == previous_bytes
    assert recovery_service.discover().document.identity.name == "First version"
    temporary = recovery_service.recovery_path.with_suffix(
        f"{recovery_service.recovery_path.suffix}.tmp"
    )
    assert not temporary.exists()


def test_restore_is_unsaved_and_requires_explicit_save(
    recovery_service: WorkspaceRecoveryService,
) -> None:
    recovery_service.save(_dirty_workspace("Recovered audit"))
    restored = WorkspaceState()

    document = recovery_service.restore(restored)

    assert document.identity.name == "Recovered audit"
    assert restored.workspace_identity == document.identity
    assert restored.workspace_file_path is None
    assert restored.is_dirty
    assert restored.get_procedure_parameters("GL003") == {"include_public_holidays": True}


def test_corrupt_or_temporary_recovery_is_not_silently_restored(
    recovery_service: WorkspaceRecoveryService,
) -> None:
    recovery_service.recovery_path.parent.mkdir(parents=True)
    temporary = recovery_service.recovery_path.with_suffix(
        f"{recovery_service.recovery_path.suffix}.tmp"
    )
    temporary.write_text("incomplete", encoding="utf-8")

    assert recovery_service.discover() is None

    recovery_service.recovery_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(WorkspaceRecoveryError, match="corrupt"):
        recovery_service.discover()

    recovery_service.discard()
    assert not recovery_service.recovery_path.exists()
    assert not temporary.exists()
