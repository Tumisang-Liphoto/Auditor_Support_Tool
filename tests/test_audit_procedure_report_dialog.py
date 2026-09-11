"""Report export integrates canonical JSON with save/cancel/error feedback."""

import pytest

from auditor_support_tool.core.audit_procedure_report_builder import AuditProcedureReportBuilder
from auditor_support_tool.gui.dialogs import audit_procedure_report_dialog as dialogs
from tests.test_audit_procedure_report import _definition, _result


@pytest.fixture
def dialog(qtbot):
    report = AuditProcedureReportBuilder().build(definition=_definition(), result=_result())
    widget = dialogs.AuditProcedureReportDialog(report=report)
    qtbot.addWidget(widget)
    return widget


def test_cancel(dialog, monkeypatch):
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    dialog._export_report()
    assert dialog._export_worker is None
    assert dialog._export_report_button.isEnabled()


def test_export_report_complete(dialog, monkeypatch, tmp_path, qtbot):
    target = tmp_path / "report.json"
    expected = dialog.report.to_json().encode("utf-8")
    monkeypatch.setattr(
        dialogs.QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON (*.json)")
    )
    messages = []
    monkeypatch.setattr(dialogs.QMessageBox, "information", lambda *args: messages.append(args[2]))
    dialog._export_report()
    qtbot.waitUntil(lambda: dialog._export_worker is None)
    assert target.read_bytes() == expected
    assert dialog.report.to_json().encode("utf-8") == expected
    assert messages
    assert dialog._export_report_button.isEnabled()


def test_export_error(dialog, monkeypatch, tmp_path, qtbot):
    target = tmp_path / "missing" / "report.json"
    monkeypatch.setattr(
        dialogs.QFileDialog, "getSaveFileName", lambda *args: (str(target), "JSON (*.json)")
    )
    errors = []
    monkeypatch.setattr(dialogs.QMessageBox, "warning", lambda *args: errors.append(args[2]))
    dialog._export_report()
    qtbot.waitUntil(lambda: dialog._export_worker is None)
    assert errors
    assert dialog._export_report_button.isEnabled()
