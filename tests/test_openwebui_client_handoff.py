"""Tests for OpenWebUI model listing and persistent report analysis."""

from __future__ import annotations

from unittest.mock import patch

from auditor_support_tool.services.openwebui_client import (
    OpenWebUIClient,
)


class StubResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        del exc_type, exc_value, traceback

    def read(self) -> bytes:
        return self._payload


def test_list_models_returns_ids_and_names() -> None:
    response = StubResponse(b'{"data": [{"id": "model-a", "name": "Model A"},{"id": "model-b"}]}')

    with patch(
        "auditor_support_tool.services.openwebui_client.urlopen",
        return_value=response,
    ):
        models = OpenWebUIClient().list_models(
            base_url="http://ai:3000",
            api_key="sk-test",
        )

    assert tuple((model.model_id, model.name) for model in models) == (
        ("model-a", "Model A"),
        ("model-b", "model-b"),
    )


def test_analysis_uploads_report_creates_chat_and_requests_completion() -> None:
    responses = (
        StubResponse(b'{"id": "file-123"}'),
        StubResponse(b'{"id": "chat-123"}'),
        StubResponse(b'{"choices": [{"message": {"content": "Analysis"}}]}'),
    )

    with patch(
        "auditor_support_tool.services.openwebui_client.urlopen",
        side_effect=responses,
    ) as mocked:
        result = OpenWebUIClient().analyse_audit_report(
            base_url="http://ai:3000",
            api_key="sk-test",
            model="model-a",
            title="GL-006 Analysis",
            filename="report.json",
            content=b'{"report": true}',
            prompt="Analyse this report.",
        )

    assert result.chat_id == "chat-123"
    assert result.chat_url == "http://ai:3000/c/chat-123"
    assert result.uploaded_file_id == "file-123"
    assert mocked.call_count == 3

    upload_request = mocked.call_args_list[0].args[0]
    chat_request = mocked.call_args_list[1].args[0]
    completion_request = mocked.call_args_list[2].args[0]

    assert "/api/v1/files/" in upload_request.full_url
    assert chat_request.full_url == ("http://ai:3000/api/v1/chats/new")
    assert completion_request.full_url == ("http://ai:3000/api/chat/completions")
    assert upload_request.get_header("Authorization") == "Bearer sk-test"
