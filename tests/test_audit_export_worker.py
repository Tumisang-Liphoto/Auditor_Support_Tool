"""Worker dispatch, snapshots and controlled failures."""

from pathlib import Path

import pytest

from auditor_support_tool.gui.workers.audit_export_worker import AuditExportWorker
from auditor_support_tool.services.audit_export_service import AuditExportError
from tests.test_audit_procedure_report import _result


@pytest.mark.parametrize("format", ["json", "csv", "xlsx"])
def test_worker_dispatch_and_detachment(qtbot, format):
    calls = []

    class Service:
        def export_report_json(self, payload, destination):
            calls.append((payload, destination))

        export_exceptions_csv = export_report_json
        export_exceptions_xlsx = export_report_json

    result = _result()
    worker = AuditExportWorker(
        payload=result, destination="out." + format, format=format, service=Service()
    )
    result.metrics["changed"] = True
    with qtbot.waitSignal(worker.completed):
        worker.start()
    worker.wait()
    assert "changed" not in calls[0][0].metrics
    assert calls[0][1] == Path("out." + format)


@pytest.mark.parametrize("error", [AuditExportError("Controlled error"), RuntimeError("secret")])
def test_worker_error(qtbot, error):
    class Service:
        def export_report_json(self, *args):
            raise error

        export_exceptions_csv = export_report_json
        export_exceptions_xlsx = export_report_json

    worker = AuditExportWorker(
        payload=_result(), destination="out.csv", format="csv", service=Service()
    )
    with qtbot.waitSignal(worker.failed) as signal:
        worker.start()
    worker.wait()
    assert "secret" not in signal.args[0]


def test_running_export_survives_snapshot_owner_disposal(qtbot):
    from threading import Event

    from PySide6.QtWidgets import QWidget

    started, release = Event(), Event()

    class Service:
        def export_report_json(self, *args):
            started.set()
            assert release.wait(5)

        export_exceptions_csv = export_report_json
        export_exceptions_xlsx = export_report_json

    owner = QWidget()
    qtbot.addWidget(owner)
    owner.worker = AuditExportWorker(
        payload=_result(), destination="out.csv", format="csv", service=Service()
    )
    worker = owner.worker
    worker.start()
    qtbot.waitUntil(started.is_set)
    owner.close()
    owner.deleteLater()
    with qtbot.waitSignal(worker.completed):
        release.set()
    worker.wait()
