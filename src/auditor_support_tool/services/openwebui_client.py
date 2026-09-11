"""Minimal authenticated OpenWebUI API connectivity client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from auditor_support_tool.services.openwebui_settings_service import (
    normalize_openwebui_url,
)


@dataclass(frozen=True, slots=True)
class OpenWebUIConnectionResult:
    """Outcome of an authenticated OpenWebUI connectivity check."""

    success: bool
    message: str
    model_count: int = 0


class _TransportPolicyError(URLError):
    """Safe, non-secret transport-policy failure."""


class _CredentialRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.has_header("Authorization"):
            old = urlsplit(req.full_url)
            new = urlsplit(newurl)
            if (
                new.scheme.lower() != "https"
                or (old.hostname, old.port or 443) != (new.hostname, new.port or 443)
                or new.username
                or new.password
            ):
                raise _TransportPolicyError(
                    "Authenticated OpenWebUI redirects require HTTPS and the same server."
                )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class OpenWebUIClient:
    """Call the small OpenWebUI API surface needed by the desktop app."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("OpenWebUI timeout must be greater than zero.")

        self._timeout_seconds = timeout_seconds

    def test_connection(
        self,
        *,
        base_url: str,
        api_key: str,
    ) -> OpenWebUIConnectionResult:
        """Authenticate and retrieve the user's available model list."""

        normalized_url = normalize_openwebui_url(base_url)
        cleaned_key = api_key.strip()

        if cleaned_key and urlsplit(normalized_url).scheme != "https":
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "API keys require an HTTPS OpenWebUI address. "
                    "Remove the API key or configure HTTPS."
                ),
            )

        headers = {"Accept": "application/json"}
        if cleaned_key:
            headers["Authorization"] = f"Bearer {cleaned_key}"
        request = Request(
            f"{normalized_url}/api/models",
            headers=headers,
            method="GET",
        )

        try:
            with build_opener(_CredentialRedirectHandler()).open(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except _TransportPolicyError:
            return OpenWebUIConnectionResult(
                success=False,
                message="Authenticated OpenWebUI redirects require HTTPS and the same server.",
            )
        except HTTPError as error:
            if error.code in {
                401,
                403,
            }:
                return OpenWebUIConnectionResult(
                    success=False,
                    message=(
                        "OpenWebUI rejected the API key. "
                        "Check the key and your OpenWebUI permissions."
                    ),
                )

            return OpenWebUIConnectionResult(
                success=False,
                message=(f"OpenWebUI returned HTTP {error.code} while testing the connection."),
            )
        except (URLError, TimeoutError):
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "OpenWebUI could not be reached. Check the address, network or VPN connection. "
                ),
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return OpenWebUIConnectionResult(
                success=False,
                message=("OpenWebUI responded, but the model list could not be interpreted."),
            )

        models = payload.get(
            "data",
            [],
        )

        if not isinstance(models, list):
            models = []

        return OpenWebUIConnectionResult(
            success=True,
            message=(
                "Connected to OpenWebUI successfully. "
                f"{len(models)} model(s) are available to this account."
            ),
            model_count=len(models),
        )
