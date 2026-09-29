"""Tests for debounced workspace autosave and recovery lifecycle wiring."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QMainWindow, QMessageBox

from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_recovery_service import WorkspaceRecoveryError
from auditor_support_tool.core.workspace_service import WorkspaceServiceError
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.main_window import MainWindow


class FakeRecoveryService:
    """Record recovery actions without touching the file system."""

    def __init__(self) -> None:
        self.save_calls = 0
        self.discard_calls = 0
        self.fail_save = False
        self.fail_discover = False
        self.snapshot = None

    def save(self, state: WorkspaceState):
        self.save_calls += 1
        if self.fail_save:
            raise WorkspaceRecoveryError("simulated failure")
        return SimpleNamespace(modified_at=datetime.now(UTC))

    def discover(self):
        if self.fail_discover:
            raise WorkspaceRecoveryError("corrupt recovery")
        return self.snapshot

    def restore(self, state: WorkspaceState):
        identity = self.snapshot.document.identity
        state.start_workspace(identity)
        return self.snapshot.document

    def discard(self) -> None:
        self.discard_calls += 1
        self.snapshot = None


class FakeWorkspaceService:
    """Provide the MainWindow workspace methods needed by these tests."""

    def __init__(self, tmp_path: Path) -> None:
        self.default_workspace_directory = tmp_path
        self.save_calls = 0
        self.load_calls = 0
        self.fail_save = False
        self.fail_load = False

    def save_state(self, state: WorkspaceState, file_path: Path | None = None) -> Path:
        self.save_calls += 1
        if self.fail_save:
            raise WorkspaceServiceError("simulated manual save failure")
        target = file_path or state.workspace_file_path
        assert target is not None
        state.set_workspace_file_path(target)
        state.mark_saved()
        return target

    def load_into_state(
        self,
        state: WorkspaceState,
        workspace_path: Path,
        *,
        allow_source_integrity_mismatch: bool = False,
    ):
        self.load_calls += 1
        if self.fail_load:
            raise WorkspaceServiceError("simulated open failure")
        identity = WorkspaceIdentity.create(name="Loaded audit")
        state.start_workspace(identity, file_path=workspace_path)
        state.set_procedure_parameters("GL003", {"loaded": True})
        state.mark_saved()
        return SimpleNamespace(identity=identity)


class AutosaveWindow(MainWindow):
    """Exercise real autosave methods without constructing every application page."""

    def __init__(
        self,
        state: WorkspaceState,
        recovery_service: FakeRecoveryService,
        workspace_service: FakeWorkspaceService,
        *,
        interval_ms: int = 60,
    ) -> None:
        QMainWindow.__init__(self)
        self._workspace_state = state
        self._workspace_recovery_service = recovery_service
        self._workspace_service = workspace_service
        self._suppress_workspace_autosave = False
        self._autosave_status_label = QLabel(self)
        self._settings_service = SimpleNamespace(
            get_user_profile=lambda: SimpleNamespace(default_currency="LSL")
        )
        self._pages = {}
        self.routes = []
        self._setup_workspace_autosave(interval_ms=interval_ms)

    def show_route(self, route: str) -> None:
        self.routes.append(route)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Avoid lifecycle prompts during pytest widget cleanup."""

        event.accept()


@pytest.fixture
def autosave_window(tmp_path: Path, qtbot):
    state = WorkspaceState()
    recovery = FakeRecoveryService()
    workspace = FakeWorkspaceService(tmp_path)
    window = AutosaveWindow(state, recovery, workspace)
    qtbot.addWidget(window)
    return window, state, recovery, workspace


def test_persisted_changes_restart_single_shot_debounce(autosave_window, qtbot) -> None:
    window, state, recovery, _workspace = autosave_window
    state.start_workspace(WorkspaceIdentity.create(name="Debounced audit"))

    qtbot.wait(35)
    state.record_transformation(action="scope_updated")
    qtbot.wait(35)

    assert recovery.save_calls == 0
    assert window._autosave_status_label.text() == "Unsaved changes"

    qtbot.waitUntil(lambda: recovery.save_calls == 1, timeout=500)
    assert window._autosave_status_label.text().startswith("Autosaved ")
    assert state.is_dirty


def test_non_persisted_navigation_does_not_trigger_autosave(autosave_window, qtbot) -> None:
    window, _state, recovery, _workspace = autosave_window

    window.show_route("help")
    qtbot.wait(90)

    assert recovery.save_calls == 0


def test_autosave_failure_is_non_intrusive_and_state_stays_dirty(
    autosave_window,
    qtbot,
) -> None:
    window, state, recovery, _workspace = autosave_window
    recovery.fail_save = True
    state.start_workspace(WorkspaceIdentity.create(name="Failure audit"))

    qtbot.waitUntil(lambda: recovery.save_calls == 1, timeout=500)

    assert window._autosave_status_label.text() == "Autosave failed"
    assert state.is_dirty


def test_normal_workspace_load_suppresses_autosave(autosave_window, qtbot, tmp_path) -> None:
    window, state, recovery, workspace = autosave_window

    window._load_workspace_state(tmp_path / "loaded.astworkspace")
    qtbot.wait(90)

    assert workspace.load_calls == 1
    assert recovery.save_calls == 0
    assert not window._autosave_timer.isActive()
    assert not state.is_dirty


def test_successful_manual_save_clears_recovery(autosave_window, tmp_path) -> None:
    window, state, recovery, workspace = autosave_window
    target = tmp_path / "manual.astworkspace"
    state.start_workspace(WorkspaceIdentity.create(name="Manual save"))
    state.set_workspace_file_path(target)

    assert window._save_workspace()

    assert workspace.save_calls == 1
    assert recovery.discard_calls == 1
    assert not state.is_dirty
    assert not window._autosave_timer.isActive()
    assert window._autosave_status_label.text() == "Saved"


def test_failed_manual_save_preserves_recovery_and_dirty_state(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    window, state, recovery, workspace = autosave_window
    workspace.fail_save = True
    state.start_workspace(WorkspaceIdentity.create(name="Failed manual save"))
    state.set_workspace_file_path(tmp_path / "manual.astworkspace")
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)

    assert not window._save_workspace()

    assert recovery.discard_calls == 0
    assert state.is_dirty
    assert window._autosave_timer.isActive()


@pytest.mark.parametrize(
    ("decision", "transition_allowed", "discard_calls"),
    (
        (QMessageBox.StandardButton.Discard, True, 0),
        (QMessageBox.StandardButton.Cancel, False, 0),
    ),
)
def test_transition_authorization_preserves_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
    decision,
    transition_allowed,
    discard_calls,
) -> None:
    window, state, recovery, _workspace = autosave_window
    state.start_workspace(WorkspaceIdentity.create(name="Transition audit"))
    monkeypatch.setattr(QMessageBox, "exec", lambda _dialog: decision)

    assert window._confirm_workspace_transition() is transition_allowed
    assert recovery.discard_calls == discard_calls


def test_discard_then_cancel_new_audit_preserves_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, state, recovery, _workspace = autosave_window
    original_identity = WorkspaceIdentity.create(name="Current audit")
    state.start_workspace(original_identity)
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )
    rejected_dialog = SimpleNamespace(
        exec=lambda: QDialog.DialogCode.Rejected,
        workspace_identity=None,
    )
    monkeypatch.setattr(
        "auditor_support_tool.gui.main_window.NewWorkspaceDialog",
        lambda *args, **kwargs: rejected_dialog,
    )

    window._create_new_workspace()

    assert state.workspace_identity is original_identity
    assert recovery.discard_calls == 0


def test_discard_then_cancel_open_audit_preserves_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, state, recovery, workspace = autosave_window
    original_identity = WorkspaceIdentity.create(name="Current audit")
    state.start_workspace(original_identity)
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: ("", ""))

    window._open_workspace()

    assert state.workspace_identity is original_identity
    assert workspace.load_calls == 0
    assert recovery.discard_calls == 0


def test_discard_then_successful_new_audit_clears_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, state, recovery, _workspace = autosave_window
    state.start_workspace(WorkspaceIdentity.create(name="Current audit"))
    replacement = WorkspaceIdentity.create(name="Replacement audit")
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )
    accepted_dialog = SimpleNamespace(
        exec=lambda: QDialog.DialogCode.Accepted,
        workspace_identity=replacement,
    )
    monkeypatch.setattr(
        "auditor_support_tool.gui.main_window.NewWorkspaceDialog",
        lambda *args, **kwargs: accepted_dialog,
    )

    window._create_new_workspace()

    assert state.workspace_identity is replacement
    assert recovery.discard_calls == 1


def test_discard_then_successful_open_audit_clears_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window, state, recovery, workspace = autosave_window
    state.start_workspace(WorkspaceIdentity.create(name="Current audit"))
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )
    selected = tmp_path / "replacement.astworkspace"
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(selected), ""),
    )

    window._open_workspace()

    assert state.workspace_identity.name == "Loaded audit"
    assert workspace.load_calls == 1
    assert recovery.discard_calls == 1


def test_discard_then_failed_open_preserves_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window, state, recovery, workspace = autosave_window
    original_identity = WorkspaceIdentity.create(name="Current audit")
    state.start_workspace(original_identity)
    workspace.fail_load = True
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(tmp_path / "broken.astworkspace"), ""),
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)

    window._open_workspace()

    assert state.workspace_identity is original_identity
    assert recovery.discard_calls == 0
    assert window._autosave_timer.isActive()


def test_discard_then_close_clears_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, state, recovery, _workspace = autosave_window
    state.start_workspace(WorkspaceIdentity.create(name="Current audit"))
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )

    window._close_workspace()

    assert not state.has_workspace
    assert recovery.discard_calls == 1


def test_discard_then_failed_update_launch_preserves_recovery(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, state, recovery, _workspace = autosave_window
    state.start_workspace(WorkspaceIdentity.create(name="Current audit"))
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda _dialog: QMessageBox.StandardButton.Discard,
    )

    def fail_launch(_prepared) -> None:
        raise OSError("simulated launch failure")

    window._update_service = SimpleNamespace(launch_prepared_update=fail_launch)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: None)

    window._install_prepared_update(object())

    assert state.has_workspace
    assert state.is_dirty
    assert recovery.discard_calls == 0


@pytest.mark.parametrize(
    ("decision", "restored", "discarded"),
    (
        (QMessageBox.StandardButton.Yes, True, 0),
        (QMessageBox.StandardButton.Discard, False, 1),
    ),
)
def test_startup_offers_restore_or_discard(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
    decision,
    restored,
    discarded,
) -> None:
    window, state, recovery, _workspace = autosave_window
    identity = WorkspaceIdentity.create(name="Recovered audit")
    recovery.snapshot = SimpleNamespace(
        modified_at=datetime.now(UTC),
        document=SimpleNamespace(identity=identity),
    )
    monkeypatch.setattr(QMessageBox, "exec", lambda _dialog: decision)

    window._offer_workspace_recovery()

    assert state.has_workspace is restored
    assert recovery.discard_calls == discarded
    if restored:
        assert state.is_dirty
        assert state.workspace_file_path is None
        assert window.routes == ["workspace.data_sources"]
        assert window._autosave_timer.isActive()
        assert window._autosave_status_label.text() == "Unsaved changes"


def test_corrupt_startup_recovery_is_reported_and_discarded(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, state, recovery, _workspace = autosave_window
    recovery.fail_discover = True
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))

    window._offer_workspace_recovery()

    assert warnings
    assert recovery.discard_calls == 1
    assert not state.has_workspace


@pytest.mark.parametrize(("approved", "discard_calls"), ((True, 1), (False, 0)))
def test_application_close_cleanup_respects_cancel(
    autosave_window,
    monkeypatch: pytest.MonkeyPatch,
    approved,
    discard_calls,
) -> None:
    window, _state, recovery, _workspace = autosave_window
    monkeypatch.setattr(window, "_confirm_workspace_transition", lambda: approved)
    event = QCloseEvent()

    MainWindow.closeEvent(window, event)

    assert event.isAccepted() is approved
    assert recovery.discard_calls == discard_calls
