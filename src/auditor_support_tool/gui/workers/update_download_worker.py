"""Background worker for secure update download and preparation."""

from PySide6.QtCore import QThread, Signal

from auditor_support_tool.services.update_service import (
    UpdateCheckResult,
    UpdateService,
)


class UpdateDownloadWorker(QThread):
    """Download, verify and stage an update without blocking the interface."""

    progress_changed = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        update_service: UpdateService,
        result: UpdateCheckResult,
    ) -> None:
        super().__init__()
        self._update_service = update_service
        self._result = result

    def run(self) -> None:
        try:
            prepared = self._update_service.prepare_update(
                self._result,
                progress_callback=self._report_progress,
            )
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(prepared)

    def _report_progress(self, downloaded: int, total: int) -> None:
        self.progress_changed.emit(downloaded, total)
