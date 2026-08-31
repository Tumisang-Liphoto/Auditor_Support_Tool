"""Tests for authenticated OpenWebUI connectivity checks."""

from __future__ import annotations

import io
from unittest.mock import patch
from urllib.error import HTTPError

from auditor_support_tool.services.openwebui_client import (
    OpenWebUIClient,
)


class StubResponse:
    """Small context-manager response used by urllib tests."""

    def __init__(
        self,
        payload: bytes,
    ) -> None:
        self._payload = payload

    def __enter__(
        self,
    ) -> StubResponse:
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        del (
            exc_type,
            exc_value,
            traceback,
        )

    def read(
        self,
    ) -> bytes:
        return self._payload


def test_connection_uses_authenticated_models_endpoint() -> None:
    response = StubResponse(b'{"data": [{"id": "model-a"}, {"id": "model-b"}]}')

    with patch(
        "auditor_support_tool.services.openwebui_client.urlopen",
        return_value=response,
    ) as mocked:
        result = OpenWebUIClient().test_connection(
            base_url="http://internal-ai:3000",
            api_key="sk-test",
        )

    request = mocked.call_args.args[0]

    assert request.full_url == ("http://internal-ai:3000/api/models")
    assert request.get_header("Authorization") == "Bearer sk-test"
    assert result.success is True
    assert result.model_count == 2


def test_connection_reports_rejected_api_key() -> None:
    error = HTTPError(
        url="http://internal-ai:3000/api/models",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=io.BytesIO(),
    )

    with patch(
        "auditor_support_tool.services.openwebui_client.urlopen",
        side_effect=error,
    ):
        result = OpenWebUIClient().test_connection(
            base_url="http://internal-ai:3000",
            api_key="bad-key",
        )

    assert result.success is False
    assert "rejected" in result.message.lower()


def test_connection_requires_api_key() -> None:
    result = OpenWebUIClient().test_connection(
        base_url="http://internal-ai:3000",
        api_key="",
    )

    assert result.success is False
    assert "api key" in result.message.lower()
