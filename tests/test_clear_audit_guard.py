"""Central Save/Discard/Cancel protection for audit clearing."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from auditor_support_tool.core.procedure_execution_models import ProcedureExecutionStamp
from auditor_support_tool.core.workbook_package import FieldMappingStatus, PreparationStatus
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_service import WorkspaceService, WorkspaceServiceError
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.main_window import MainWindow
from auditor_support_tool.gui.pages.data_sources_page import DataSourcesPage


class TransitionWindow(MainWindow):
    """Exercise real transition/save methods without unrelated application startup."""

    def __init__(self, state, service):
        QMainWindow.__init__(self)
        self._workspace_state = state
        self._workspace_service = service
        self.routes = []

    def show_route(self, route):
        self.routes.append(route)

    def closeEvent(self, event):
        # Widget teardown must not trigger another application-exit decision.
        event.accept()


@pytest.mark.parametrize(
    ("decision", "saved_before", "save_result", "cleared"),
    (
        ("clean", True, None, True),
        ("cancel", True, None, False),
        ("discard", True, None, True),
        ("save", True, "success", True),
        ("save", False, "success", True),
        ("save", False, "cancelled", False),
        ("save", True, "failure", False),
        ("save", False, "failure", False),
    ),
)
def test_clear_audit_uses_central_transition_guard(
    tmp_path, qtbot, monkeypatch, decision, saved_before, save_result, cleared
):
    source = tmp_path / "source.csv"
    source.write_text("Invoice,Amount\nINV001,125\n", encoding="utf-8")
    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Edited audit", description="Keep scope"))
    package = WorkbookPackageService().build_package(source)
    dataset = package.datasets[0]
    dataset.preparation_status = PreparationStatus.CONFIRMED
    dataset.columns[0].confirmed_name = "Prepared invoice"
    dataset.field_mappings = {dataset.columns[0].column_id: "invoice_number"}
    dataset.mapping_status = FieldMappingStatus.CONFIRMED
    state.set_workbook_package(package)
    state.record_transformation(action="reviewed_mapping", details={"reviewer": "Auditor"})
    state.record_procedure_execution(
        ProcedureExecutionStamp.create(
            execution_id="previous-run",
            procedure_id="GL001",
            procedure_version="1.0",
            dataset_id=dataset.dataset_id,
            source_sha256=dataset.loaded_table.source_sha256,
            mapping_fingerprint="b" * 64,
            completed_at="2026-09-11T00:00:00+00:00",
        )
    )
    service = WorkspaceService(
        SimpleNamespace(workspaces=tmp_path / "audits", workspace_backups=tmp_path / "backups")
    )
    target = tmp_path / "audits" / "audit.astworkspace"
    if saved_before:
        state.set_workspace_file_path(target)
    if decision == "clean":
        state.mark_saved()
    before = deepcopy(service.build_document(state))
    identity = state.workspace_identity
    events = []
    window = TransitionWindow(state, service)
    qtbot.addWidget(window)
    page = DataSourcesPage(workspace_state=state)
    qtbot.addWidget(page)
    page.clear_requested.connect(window._close_workspace)
    state.workspace_cleared.connect(lambda: events.append("clear"))
    real_save = service.save_state

    def save(*args, **kwargs):
        events.append("save")
        assert state.has_workspace
        assert service.build_document(state) == before
        if save_result == "failure":
            raise WorkspaceServiceError("Test save failure")
        result = real_save(*args, **kwargs)
        events.append("saved")
        return result

    def prompt(dialog):
        events.append("prompt")
        assert dialog.standardButtons() == (
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        return getattr(QMessageBox.StandardButton, decision.capitalize())

    def choose_save_path(*args, **kwargs):
        events.append("save_as")
        return ("" if save_result == "cancelled" else str(target), "")

    monkeypatch.setattr(service, "save_state", save)
    monkeypatch.setattr(QMessageBox, "exec", prompt)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: events.append("save_error"))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", choose_save_path)
    page._clear_workspace()

    assert events.count("prompt") == (0 if decision == "clean" else 1)
    assert events.count("clear") == int(cleared)
    assert events.count("save") == int(save_result in {"success", "failure"})
    assert events.count("save_as") == int(decision == "save" and not saved_before)
    assert events.count("save_error") == int(save_result == "failure")
    if cleared:
        assert not state.has_workspace
        assert not state.is_dirty
        assert state.workbook_package is None
        assert not state.transformation_history
        assert not state.procedure_execution_stamps
        assert window.routes == ["dashboard"]
        if save_result == "success":
            assert events.index("saved") < events.index("clear")
            assert replace(service.load_document(target), source=before.source) == before
    else:
        assert state.workspace_identity is identity
        assert state.workbook_package is package
        assert state.is_dirty
        assert service.build_document(state) == before
        assert window.routes == []
