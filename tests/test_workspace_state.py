"""Tests for active audit workspace state."""

from dataclasses import replace
from pathlib import Path

import pytest

from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_state import WorkspaceState


def test_workspace_state_starts_without_workspace() -> None:
    """A new state contains no active workspace."""

    state = WorkspaceState()

    assert state.has_workspace is False
    assert state.workspace_identity is None
    assert state.workspace_file_path is None
    assert state.is_dirty is False


def test_start_new_workspace_marks_state_dirty() -> None:
    """A newly created workspace has not yet been saved."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="General Ledger Audit")

    state.start_workspace(identity)

    assert state.has_workspace is True
    assert state.workspace_identity is identity
    assert state.workspace_file_path is None
    assert state.is_dirty is True


def test_start_saved_workspace_marks_state_clean(
    tmp_path: Path,
) -> None:
    """A workspace opened from a saved file starts clean."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="General Ledger Audit")
    workspace_path = tmp_path / "general-ledger.astworkspace"

    state.start_workspace(
        identity,
        file_path=workspace_path,
    )

    assert state.has_workspace is True
    assert state.workspace_file_path == workspace_path.resolve()
    assert state.is_dirty is False


def test_mark_dirty_requires_active_workspace() -> None:
    """State without an active workspace remains clean."""

    state = WorkspaceState()

    state.mark_dirty()

    assert state.is_dirty is False


def test_mark_saved_clears_dirty_state() -> None:
    """Saving clears the unsaved-change indicator."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="Payroll Audit")

    state.start_workspace(identity)

    assert state.is_dirty is True

    state.mark_saved()

    assert state.is_dirty is False


def test_set_workspace_file_path_resolves_path(
    tmp_path: Path,
) -> None:
    """Workspace paths are stored as resolved paths."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="Payroll Audit")
    workspace_path = tmp_path / "payroll.astworkspace"

    state.start_workspace(identity)
    state.set_workspace_file_path(workspace_path)

    assert state.workspace_file_path == workspace_path.resolve()


def test_clear_removes_workspace_identity_and_dirty_state() -> None:
    """Clearing removes all workspace-level state."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="Payroll Audit")

    state.start_workspace(identity)
    state.clear()

    assert state.has_workspace is False
    assert state.workspace_identity is None
    assert state.workspace_file_path is None
    assert state.is_dirty is False


def test_update_workspace_identity_records_auditable_change(
    tmp_path: Path,
) -> None:
    """Editing audit details should preserve identity and record the change."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(
        name="General Ledger Audit",
        auditee_name="Example Ministry",
        audit_year="2026",
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
        audit_domain="Financial Audit",
    )
    workspace_path = tmp_path / "general-ledger.astworkspace"

    state.start_workspace(identity, file_path=workspace_path)

    changed_fields = state.update_workspace_identity(
        replace(
            identity,
            name="Updated General Ledger Audit",
            audit_period_end="2027-03-31",
        )
    )

    updated = state.workspace_identity

    assert updated is not None
    assert updated.workspace_id == identity.workspace_id
    assert updated.created_at == identity.created_at
    assert updated.name == "Updated General Ledger Audit"
    assert updated.audit_period_end == "2027-03-31"
    assert changed_fields == ("name", "audit_period_end")
    assert state.is_dirty is True
    assert len(state.transformation_history) == 1

    record = state.transformation_history[0]

    assert record.action == "audit_details_updated"
    assert record.old_value["name"] == "General Ledger Audit"
    assert record.new_value["name"] == "Updated General Ledger Audit"
    assert record.details["changed_fields"] == ["name", "audit_period_end"]
    assert record.details["audit_period_changed"] is True


def test_update_workspace_identity_no_change_keeps_saved_state_clean(
    tmp_path: Path,
) -> None:
    """Opening the editor and saving unchanged values should be a no-op."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(name="Payroll Audit")

    state.start_workspace(
        identity,
        file_path=tmp_path / "payroll.astworkspace",
    )

    changed_fields = state.update_workspace_identity(replace(identity))

    assert changed_fields == ()
    assert state.is_dirty is False
    assert state.transformation_history == ()


def test_update_workspace_identity_rejects_another_audit() -> None:
    """Editing must never replace the active audit with another audit identity."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit A"))

    with pytest.raises(ValueError, match="belong to the active audit"):
        state.update_workspace_identity(WorkspaceIdentity.create(name="Audit B"))


def test_update_workspace_identity_locks_domain_after_data_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Audit domain should be immutable once a workbook package exists."""

    state = WorkspaceState()
    identity = WorkspaceIdentity.create(
        name="General Ledger Audit",
        audit_domain="Financial Audit",
    )
    state.start_workspace(
        identity,
        file_path=tmp_path / "general-ledger.astworkspace",
    )
    monkeypatch.setattr(state, "_workbook_package", object())

    with pytest.raises(
        ValueError,
        match="cannot be changed after source data has been loaded",
    ):
        state.update_workspace_identity(replace(identity, audit_domain="Compliance Audit"))

    assert state.workspace_identity is identity
    assert state.is_dirty is False
    assert state.transformation_history == ()
