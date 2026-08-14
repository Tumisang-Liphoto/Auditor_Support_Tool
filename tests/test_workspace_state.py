"""Tests for active audit workspace state."""

from pathlib import Path

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
