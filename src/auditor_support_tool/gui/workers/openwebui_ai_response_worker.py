"""Background worker for a small OpenWebUI AI response test."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from auditor_support_tool.services.openwebui_client import OpenWebUIClient


class OpenWebUIAIResponseWorker(QThread):
    """Request one model response without blocking the interface."""

    completed = Signal(object)

    def __init__(
        self,
        *,
        client: OpenWebUIClient,
        base_url: str,
        api_key: str,
        model_id: str,
    ) -> None:
        super().__init__()

        self._client = client
        self._base_url = base_url
        self._api_key = api_key
        self._model_id = model_id

    def run(self) -> None:
        """Run the model-inference connectivity check."""

        result = self._client.test_ai_response(
            base_url=self._base_url,
            api_key=self._api_key,
            model_id=self._model_id,
        )

        self.completed.emit(result)
