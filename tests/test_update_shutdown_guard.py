"""Update launch must follow the normal audit transition guard."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.main_window import MainWindow
from auditor_support_tool.gui.pages.updates_page import UpdatesPage
from auditor_support_tool.services.settings_service import SettingsService
from tests.test_clear_audit_guard import TransitionWindow


@pytest.mark.parametrize(
    ("decision", "save_ok", "launch"),
    [
        ("Cancel", False, False),
        ("Discard", False, True),
        ("Save", True, True),
        ("Save", False, False),
    ],
)
def test_guard_precedes_update_launch(qtbot, monkeypatch, decision, save_ok, launch):
    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Unsaved audit"))
    window = TransitionWindow(state, None)
    qtbot.addWidget(window)
    calls = []
    window._update_service = SimpleNamespace(
        launch_prepared_update=lambda p: calls.append("launch")
    )

    def save():
        calls.append("save")
        return save_ok

    monkeypatch.setattr(window, "_save_workspace", save)

    def prompt(box):
        calls.append("prompt")
        return getattr(QMessageBox.StandardButton, decision)

    monkeypatch.setattr(QMessageBox, "exec", prompt)

    def close():
        calls.append("close")
        event = QCloseEvent()
        MainWindow.closeEvent(window, event)
        assert event.isAccepted()

    monkeypatch.setattr(window, "close", close)
    window._install_prepared_update(object())
    assert ("launch" in calls) is launch
    assert ("close" in calls) is launch
    assert calls.count("prompt") == 1
    if launch:
        assert calls.index("prompt") < calls.index("launch") < calls.index("close")
    if decision == "Save" and launch:
        assert calls.index("save") < calls.index("launch")
    assert state.has_workspace
    assert not getattr(window, "_update_shutdown_approved", False)
    monkeypatch.delattr(window, "close")


def test_launch_failure_does_not_close_or_bypass_future_guard(qtbot, monkeypatch):
    window = TransitionWindow(WorkspaceState(), None)
    qtbot.addWidget(window)
    window._update_service = SimpleNamespace(
        launch_prepared_update=Mock(side_effect=OSError("private"))
    )
    close = Mock()
    monkeypatch.setattr(window, "close", close)
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: errors.append(args[2]))
    window._install_prepared_update(object())
    close.assert_not_called()
    assert errors and "private" not in errors[0]
    assert not getattr(window, "_update_shutdown_approved", False)
    monkeypatch.delattr(window, "close")


def test_updates_page_requests_authorization_without_launching(qtbot, tmp_path):
    service = SimpleNamespace(launch_prepared_update=Mock())
    page = UpdatesPage(SettingsService(tmp_path / "settings.ini"), service)
    qtbot.addWidget(page)
    prepared = object()
    with qtbot.waitSignal(page.installation_requested) as signal:
        page._handle_update_prepared(prepared)
    assert signal.args == [prepared]
    service.launch_prepared_update.assert_not_called()
