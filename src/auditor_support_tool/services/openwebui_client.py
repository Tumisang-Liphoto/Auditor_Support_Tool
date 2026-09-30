"""Minimal authenticated OpenWebUI API connectivity client."""

from __future__ import annotations

import json
import ssl
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

from auditor_support_tool.services.openwebui_settings_service import (
    normalize_openwebui_url,
)

_OPENWEBUI_CA_FILENAME = "openwebui-caddy-root.crt"


def _bundled_openwebui_ca_path() -> Path:
    """Return the bundled CA used to trust the approved internal OpenWebUI."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        application_root = Path(sys._MEIPASS) / "auditor_support_tool"
    else:
        application_root = Path(__file__).resolve().parents[1]

    return (
        application_root
        / "resources"
        / "certificates"
        / _OPENWEBUI_CA_FILENAME
    )


def _openwebui_ssl_context(
    ca_certificate_path: Path | None = None,
) -> ssl.SSLContext:
    """Build normal HTTPS trust plus the approved internal OpenWebUI CA."""

    context = ssl.create_default_context()

    certificate_path = (
        ca_certificate_path
        if ca_certificate_path is not None
        else _bundled_openwebui_ca_path()
    )

    if certificate_path.is_file():
        context.load_verify_locations(
            cafile=str(certificate_path)
        )

    return context


@dataclass(frozen=True, slots=True)
class OpenWebUIModel:
    """One model exposed to the authenticated OpenWebUI account."""

    model_id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class OpenWebUIConnectionResult:
    """Outcome of an authenticated OpenWebUI connectivity check."""

    success: bool
    message: str
    model_count: int = 0
    models: tuple[OpenWebUIModel, ...] = ()


class _TransportPolicyError(URLError):
    """Safe, non-secret transport-policy failure."""


class _CredentialRedirectHandler(HTTPRedirectHandler):
    """Prevent authenticated requests from redirecting unsafely."""

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        if req.has_header("Authorization"):
            old = urlsplit(req.full_url)
            new = urlsplit(newurl)

            if (
                new.scheme.lower() != "https"
                or (
                    old.hostname,
                    old.port or 443,
                )
                != (
                    new.hostname,
                    new.port or 443,
                )
                or new.username
                or new.password
            ):
                raise _TransportPolicyError(
                    "Authenticated OpenWebUI redirects require HTTPS "
                    "and the same server."
                )

        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )


class OpenWebUIClient:
    """Call the small OpenWebUI API surface needed by the desktop app."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        ca_certificate_path: Path | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "OpenWebUI timeout must be greater than zero."
            )

        self._timeout_seconds = timeout_seconds
        self._ca_certificate_path = ca_certificate_path

    def test_connection(
        self,
        *,
        base_url: str,
        api_key: str,
    ) -> OpenWebUIConnectionResult:
        """Authenticate and retrieve the user's available model list."""

        normalized_url = normalize_openwebui_url(base_url)
        cleaned_key = api_key.strip()

        if (
            cleaned_key
            and urlsplit(normalized_url).scheme != "https"
        ):
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "API keys require an HTTPS OpenWebUI address. "
                    "Remove the API key or configure HTTPS."
                ),
            )

        headers = {
            "Accept": "application/json",
        }

        if cleaned_key:
            headers["Authorization"] = f"Bearer {cleaned_key}"

        request = Request(
            f"{normalized_url}/api/models",
            headers=headers,
            method="GET",
        )

        handlers = [
            _CredentialRedirectHandler(),
        ]

        if urlsplit(normalized_url).scheme == "https":
            try:
                ssl_context = _openwebui_ssl_context(
                    self._ca_certificate_path
                )
            except (
                OSError,
                ssl.SSLError,
            ):
                return OpenWebUIConnectionResult(
                    success=False,
                    message=(
                        "OpenWebUI HTTPS trust could not be "
                        "initialized. Check the application "
                        "installation."
                    ),
                )

            handlers.append(
                HTTPSHandler(
                    context=ssl_context,
                )
            )

        try:
            with build_opener(
                *handlers
            ).open(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )

        except _TransportPolicyError:
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "Authenticated OpenWebUI redirects require "
                    "HTTPS and the same server."
                ),
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
                message=(
                    f"OpenWebUI returned HTTP {error.code} "
                    "while testing the connection."
                ),
            )

        except (
            URLError,
            TimeoutError,
        ):
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "OpenWebUI could not be reached. "
                    "Check the address, network or VPN connection."
                ),
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "OpenWebUI responded, but the model list "
                    "could not be interpreted."
                ),
            )

        raw_models = (
            payload.get(
                "data",
                [],
            )
            if isinstance(payload, dict)
            else []
        )

        models: list[OpenWebUIModel] = []
        seen_model_ids: set[str] = set()

        if isinstance(raw_models, list):
            for raw_model in raw_models:
                if not isinstance(raw_model, dict):
                    continue

                raw_model_id = raw_model.get("id")
                if not isinstance(raw_model_id, str):
                    continue

                model_id = raw_model_id.strip()
                if not model_id or model_id in seen_model_ids:
                    continue

                raw_display_name = raw_model.get("name")
                display_name = (
                    raw_display_name.strip()
                    if isinstance(raw_display_name, str) and raw_display_name.strip()
                    else model_id
                )

                models.append(
                    OpenWebUIModel(
                        model_id=model_id,
                        display_name=display_name,
                    )
                )
                seen_model_ids.add(model_id)

        available_models = tuple(models)

        return OpenWebUIConnectionResult(
            success=True,
            message=(
                "Connected to OpenWebUI successfully. "
                f"{len(available_models)} model(s) are available "
                "to this account."
            ),
            model_count=len(available_models),
            models=available_models,
        )
