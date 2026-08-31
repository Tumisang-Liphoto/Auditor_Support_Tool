"""Background worker for OpenWebUI connection testing."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from auditor_support_tool.services.openwebui_client import (
    OpenWebUIClient,
)


class OpenWebUIConnectionWorker(QThread):
    """Test OpenWebUI connectivity without blocking the interface."""

    completed = Signal(object)

    def __init__(
        self,
        *,
        client: OpenWebUIClient,
        base_url: str,
        api_key: str,
    ) -> None:
        super().__init__()

        self._client = client
        self._base_url = base_url
        self._api_key = api_key

    def run(self) -> None:
        """Run the authenticated connectivity check."""

        result = self._client.test_connection(
            base_url=self._base_url,
            api_key=self._api_key,
        )

        self.completed.emit(result)
