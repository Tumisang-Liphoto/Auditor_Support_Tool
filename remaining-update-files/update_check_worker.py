"""Background worker for GitHub update checks."""

from PySide6.QtCore import QThread, Signal

from auditor_support_tool.services.update_service import (
    UpdateService,
)


class UpdateCheckWorker(QThread):
    """Run an update check without blocking the interface."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        update_service: UpdateService,
        channel: str,
    ) -> None:
        super().__init__()

        self._update_service = update_service
        self._channel = channel

    def run(self) -> None:
        """Check GitHub and emit the resulting status."""

        try:
            result = self._update_service.check_for_updates(self._channel)
        except Exception as error:
            self.failed.emit(f"Unexpected update-check error: {error}")
            return

        self.completed.emit(result)
