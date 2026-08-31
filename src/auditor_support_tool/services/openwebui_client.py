"""Minimal authenticated OpenWebUI API connectivity client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from auditor_support_tool.services.openwebui_settings_service import (
    normalize_openwebui_url,
)


@dataclass(frozen=True, slots=True)
class OpenWebUIConnectionResult:
    """Outcome of an authenticated OpenWebUI connectivity check."""

    success: bool
    message: str
    model_count: int = 0


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

        if not cleaned_key:
            return OpenWebUIConnectionResult(
                success=False,
                message=("No OpenWebUI API key is configured for this address."),
            )

        request = Request(
            f"{normalized_url}/api/models",
            headers={
                "Accept": "application/json",
                "Authorization": (f"Bearer {cleaned_key}"),
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
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
        except (URLError, TimeoutError) as error:
            return OpenWebUIConnectionResult(
                success=False,
                message=(
                    "OpenWebUI could not be reached. "
                    "Check the address, network or VPN connection. "
                    f"Details: {error}"
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
