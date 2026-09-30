"""Warm execution-status source hashes outside the GUI thread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Slot

from auditor_support_tool.core.procedure_execution_status_service import (
    ProcedureExecutionStatusService,
)


class SourceHashWorker(QThread):
    """Calculate one status-cache source hash without blocking the GUI thread."""

    _active: set = set()

    def __init__(
        self,
        *,
        status_service: ProcedureExecutionStatusService,
        source_path: str | Path,
        source_signature: tuple[str, int, int],
    ) -> None:
        super().__init__(QCoreApplication.instance())
        self._status_service = status_service
        self.source_path = Path(source_path).expanduser().resolve()
        self.source_signature = source_signature
        self.error: Exception | None = None
        self.finished.connect(self._release)

    def start(self) -> None:
        self._active.add(self)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown)
        super().start()

    def run(self) -> None:
        try:
            self._status_service.refresh_source_hash(self.source_path)
        except Exception as error:
            self.error = error

    @Slot()
    def _shutdown(self) -> None:
        self.wait()

    @Slot()
    def _release(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            try:
                app.aboutToQuit.disconnect(self._shutdown)
            except (RuntimeError, TypeError):
                pass
        self._active.discard(self)
        self.deleteLater()
