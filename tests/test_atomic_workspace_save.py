"""Failure injection protects the last complete workspace/source pair."""

from pathlib import Path

import pytest

from auditor_support_tool.core import workspace_service as module
from auditor_support_tool.core.source_integrity_service import SourceIntegrityService
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_service import WorkspaceService, WorkspaceServiceError
from auditor_support_tool.core.workspace_state import WorkspaceState
from tests.test_source_integrity_service import create_paths


def setup_audit(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("Code,Amount\nOLD,100\n", encoding="utf-8")
    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Transactional audit"))
    state.set_workbook_package(WorkbookPackageService().build_package(source))
    service = WorkspaceService(create_paths(tmp_path))
    target = service.default_workspace_directory / "audit.astworkspace"
    return service, state, source, target


def reload_changed_source(state, source):
    source.write_text("Code,Amount\nNEW,999\n", encoding="utf-8")
    state.set_workbook_package(WorkbookPackageService().build_package(source))
    state.workspace_identity.description = "New save"


def referenced_source(service, workspace):
    document = service.load_document(workspace)
    return service._resolve_workspace_source_path(document.source, workspace)


def inject_failure(monkeypatch, service, target, phase):
    if phase == "copy":

        def fail_copy(source, destination):
            Path(destination).write_bytes(b"partial copy")
            raise OSError("Injected source copy failure")

        monkeypatch.setattr(module.shutil, "copy2", fail_copy)
    elif phase == "serialize":
        original = module.json.dumps

        def fail_serialization(value, *args, **kwargs):
            if (
                isinstance(value, dict)
                and value.get("identity", {}).get("description") == "New save"
            ):
                raise TypeError("Injected serialization failure")
            return original(value, *args, **kwargs)

        monkeypatch.setattr(module.json, "dumps", fail_serialization)
    elif phase == "validate":
        original = service._verify_written_document

        def fail_validation(path):
            if path == target.with_suffix(".astworkspace.tmp"):
                raise WorkspaceServiceError("Injected staged validation failure")
            return original(path)

        monkeypatch.setattr(service, "_verify_written_document", fail_validation)
    else:
        original = Path.replace

        def fail_replace(path, destination):
            if Path(destination) == target:
                raise OSError("Injected final document replacement failure")
            return original(path, destination)

        monkeypatch.setattr(Path, "replace", fail_replace)


@pytest.mark.parametrize("phase", ("copy", "serialize", "validate", "replace"))
def test_failed_changed_source_save_preserves_previous_pair(tmp_path, monkeypatch, phase):
    service, state, source, target = setup_audit(tmp_path)
    service.save_state(state, target)
    old_source = referenced_source(service, target)
    old_document_bytes, old_source_bytes = target.read_bytes(), old_source.read_bytes()
    reload_changed_source(state, source)
    inject_failure(monkeypatch, service, target, phase)
    with pytest.raises(WorkspaceServiceError, match="Injected"):
        service.save_state(state)
    assert state.is_dirty
    assert state.workspace_file_path == target
    assert target.read_bytes() == old_document_bytes
    assert old_source.read_bytes() == old_source_bytes
    assert service.load_document(target).source.sha256 == SourceIntegrityService().sha256_file(
        old_source
    )
    reopened = WorkspaceState()
    service.load_into_state(reopened, target)
    assert reopened.active_dataset.loaded_table.rows[0]["Code"] == "OLD"
    assets = target.parent / "audit.astdata"
    assert {path for path in assets.rglob("*") if path.is_file()} == {old_source}
    assert not list(target.parent.rglob("*.tmp"))


@pytest.mark.parametrize("save_as", (False, True))
@pytest.mark.parametrize("phase", ("copy", "serialize", "validate", "replace"))
def test_first_save_or_save_as_failure_leaves_no_false_workspace(
    tmp_path, monkeypatch, save_as, phase
):
    service, state, source, old_target = setup_audit(tmp_path)
    if save_as:
        service.save_state(state, old_target)
        old_document_bytes = old_target.read_bytes()
        old_source = referenced_source(service, old_target)
        old_source_bytes = old_source.read_bytes()
    reload_changed_source(state, source)
    target = old_target.with_name("new.astworkspace")
    inject_failure(monkeypatch, service, target, phase)
    with pytest.raises(WorkspaceServiceError, match="Injected"):
        service.save_state(state, target)
    assert state.is_dirty
    assert state.workspace_file_path == (old_target if save_as else None)
    assert not target.exists()
    assert not [p for p in (target.parent / "new.astdata").rglob("*") if p.is_file()]
    assert not list(target.parent.rglob("*.tmp"))
    if save_as:
        assert old_target.read_bytes() == old_document_bytes
        assert old_source.read_bytes() == old_source_bytes
        service.load_into_state(WorkspaceState(), old_target)


def test_successful_reload_save_preserves_old_source_and_reopenable_backup(tmp_path, monkeypatch):
    service, state, source, target = setup_audit(tmp_path)
    service.save_state(state, target)
    old_source = referenced_source(service, target)
    old_bytes = old_source.read_bytes()
    reload_changed_source(state, source)
    service.save_state(state)
    new_source = referenced_source(service, target)
    assert new_source != old_source
    assert old_source.read_bytes() == old_bytes
    assert new_source.read_bytes() == source.read_bytes()
    assert not state.is_dirty
    reopened = WorkspaceState()
    service.load_into_state(reopened, target)
    assert reopened.active_dataset.loaded_table.rows[0]["Code"] == "NEW"
    backup = next(service._application_paths.workspace_backups.rglob("*.astworkspace"))
    previous = WorkspaceState()
    service.load_into_state(previous, backup)
    assert previous.active_dataset.loaded_table.rows[0]["Code"] == "OLD"
    # Missing original: use the committed (versioned) reference, including Save As.
    source.unlink()
    state.mark_dirty()
    service.save_state(state)
    service.save_state(state, target.with_name("copy.astworkspace"))
    service.load_into_state(WorkspaceState(), target.with_name("copy.astworkspace"))


def test_unchanged_save_reuses_existing_managed_bytes(tmp_path, monkeypatch):
    service, state, source, target = setup_audit(tmp_path)
    service.save_state(state, target)
    managed = referenced_source(service, target)

    def unexpected_copy(*args):
        pytest.fail("Unchanged managed source must not be replaced")

    monkeypatch.setattr(service, "_copy_source_if_needed", unexpected_copy)
    state.mark_dirty()
    service.save_state(state)
    assert referenced_source(service, target) == managed
    service.load_into_state(WorkspaceState(), target)
