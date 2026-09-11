"""Tests for authenticated OpenWebUI connectivity checks."""

from __future__ import annotations

import io
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from auditor_support_tool.services.openwebui_client import (
    OpenWebUIClient,
    _CredentialRedirectHandler,
    _TransportPolicyError,
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
        "auditor_support_tool.services.openwebui_client.build_opener",
        return_value=Mock(open=Mock(return_value=response)),
    ) as mocked:
        result = OpenWebUIClient().test_connection(
            base_url="https://internal-ai:3000",
            api_key="sk-test",
        )

    request = mocked.return_value.open.call_args.args[0]

    assert request.full_url == ("https://internal-ai:3000/api/models")
    assert request.get_header("Authorization") == "Bearer sk-test"
    assert result.success is True
    assert result.model_count == 2


def test_connection_reports_rejected_api_key() -> None:
    error = HTTPError(
        url="https://internal-ai:3000/api/models",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=io.BytesIO(),
    )

    with patch(
        "auditor_support_tool.services.openwebui_client.build_opener",
        return_value=Mock(open=Mock(side_effect=error)),
    ):
        result = OpenWebUIClient().test_connection(
            base_url="https://internal-ai:3000",
            api_key="bad-key",
        )

    assert result.success is False
    assert "rejected" in result.message.lower()


@pytest.mark.parametrize("url", ["https://internal-ai", "http://internal-ai"])
def test_connection_without_api_key(url):
    with patch("auditor_support_tool.services.openwebui_client.build_opener") as factory:
        factory.return_value.open.return_value = StubResponse(b'{"data": []}')
        result = OpenWebUIClient().test_connection(base_url=url, api_key="")
    assert result.success
    assert not factory.return_value.open.call_args.args[0].has_header("Authorization")


@pytest.mark.parametrize(
    "url",
    [
        "http://internal-ai",
        "internal-ai:3000",
        "http://localhost",
        "http://127.0.0.1",
        "http://[::1]",
    ],
)
def test_plaintext_credentials_blocked_before_io(url):
    secret = "synthetic-transport-secret"
    with patch("auditor_support_tool.services.openwebui_client.build_opener") as factory:
        result = OpenWebUIClient().test_connection(base_url=url, api_key=secret)
    factory.assert_not_called()
    assert not result.success
    assert "API keys require an HTTPS" in result.message
    assert secret not in repr(result)


@pytest.mark.parametrize("target", ["http://internal-ai/next", "https://other-server/next"])
def test_authenticated_redirect_blocked_before_forwarding(target):
    handler = _CredentialRedirectHandler()
    handler.parent = Mock()
    request = Request(
        "https://internal-ai/api/models", headers={"Authorization": "Bearer synthetic"}
    )
    with pytest.raises(_TransportPolicyError) as caught:
        handler.http_error_302(request, io.BytesIO(), 302, "Found", {"location": target})
    handler.parent.open.assert_not_called()
    assert "synthetic" not in str(caught.value)


def test_same_server_https_redirect_preserves_authorization():
    request = Request(
        "https://internal-ai/api/models", headers={"Authorization": "Bearer synthetic"}
    )
    redirected = _CredentialRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, "https://internal-ai/next"
    )
    assert redirected.get_header("Authorization") == request.get_header("Authorization")


def test_unauthenticated_http_redirect_allowed():
    request = Request("http://internal-ai/api/models")
    redirected = _CredentialRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, "http://internal-ai/next"
    )
    assert not redirected.has_header("Authorization")


@pytest.mark.parametrize(
    "error", [URLError("synthetic-secret"), _TransportPolicyError("synthetic-secret")]
)
def test_network_errors_do_not_echo_secrets(error):
    with patch("auditor_support_tool.services.openwebui_client.build_opener") as factory:
        factory.return_value.open.side_effect = error
        result = OpenWebUIClient().test_connection(
            base_url="https://internal-ai", api_key="synthetic-secret"
        )
    assert not result.success
    assert "synthetic-secret" not in repr(result)


@pytest.mark.parametrize("code", [301, 302, 303, 307, 308])
def test_real_opener_dispatch_rejects_authenticated_downgrade(code):
    from email.message import Message
    from urllib.response import addinfourl

    headers = Message()
    headers["Location"] = "http://internal-ai/next"
    response = addinfourl(io.BytesIO(), headers, "https://internal-ai/api/models", code)
    response.msg = "Redirect"
    with (
        patch("urllib.request.HTTPSHandler.https_open", return_value=response) as https,
        patch("urllib.request.HTTPHandler.http_open") as http,
    ):
        result = OpenWebUIClient().test_connection(
            base_url="https://internal-ai", api_key="synthetic-redirect-secret"
        )
    https.assert_called_once()
    http.assert_not_called()
    assert not result.success
    assert "redirects require HTTPS" in result.message
    assert "synthetic-redirect-secret" not in repr(result)
