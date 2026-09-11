"""Background output worker retaining a detached run snapshot."""

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Signal

from auditor_support_tool.services.audit_export_service import AuditExportError, AuditExportService


class AuditExportWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)
    _active = set()

    def __init__(self, *, payload, destination: str, format: str, service=None):
        # Application ownership keeps running threads alive if their page/dialog closes.
        super().__init__(QCoreApplication.instance())
        self._payload = deepcopy(payload)
        self._destination = Path(destination)
        self._format = format
        self._service = service or AuditExportService()
        self.finished.connect(self._release)

    def start(self, *args):
        self._active.add(self)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.wait)
        super().start(*args)

    def _release(self):
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.disconnect(self.wait)
        self._active.discard(self)
        self.deleteLater()

    def run(self):
        try:
            methods = {
                "json": self._service.export_report_json,
                "csv": self._service.export_exceptions_csv,
                "xlsx": self._service.export_exceptions_xlsx,
            }
            methods[self._format](self._payload, self._destination)
        except AuditExportError as error:
            self.failed.emit(str(error))
        except Exception:
            self.failed.emit("Export could not be completed. No audit state was changed.")
        else:
            self.completed.emit(self._destination)
