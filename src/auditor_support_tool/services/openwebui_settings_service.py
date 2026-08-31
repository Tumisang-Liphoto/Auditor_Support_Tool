"""Persistent OpenWebUI configuration with secure credential storage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from PySide6.QtCore import QSettings

from auditor_support_tool.services.windows_credential_service import (
    CredentialStore,
)

_CREDENTIAL_PREFIX = "Auditor Support Tool/OpenWebUI/API Key"


@dataclass(frozen=True, slots=True)
class OpenWebUISettings:
    """Non-secret per-user OpenWebUI configuration."""

    enabled: bool = False
    base_url: str = ""


class OpenWebUISettingsService:
    """Persist OpenWebUI configuration while keeping API keys out of INI."""

    def __init__(
        self,
        *,
        settings_file: Path,
        credential_store: CredentialStore,
    ) -> None:
        settings_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._settings = QSettings(
            str(settings_file),
            QSettings.Format.IniFormat,
        )
        self._credential_store = credential_store

    def get_settings(
        self,
    ) -> OpenWebUISettings:
        """Return the saved non-secret OpenWebUI settings."""

        return OpenWebUISettings(
            enabled=self._read_bool(
                "ai/openwebui/enabled",
                False,
            ),
            base_url=self._read_string(
                "ai/openwebui/base_url",
                "",
            ),
        )

    def save_settings(
        self,
        settings: OpenWebUISettings,
    ) -> OpenWebUISettings:
        """Validate and save the non-secret OpenWebUI settings."""

        normalized_url = (
            normalize_openwebui_url(settings.base_url) if settings.base_url.strip() else ""
        )

        if settings.enabled and not normalized_url:
            raise ValueError("An OpenWebUI address is required when AI access is enabled.")

        normalized = OpenWebUISettings(
            enabled=bool(settings.enabled),
            base_url=normalized_url,
        )

        self._settings.setValue(
            "ai/openwebui/enabled",
            normalized.enabled,
        )
        self._settings.setValue(
            "ai/openwebui/base_url",
            normalized.base_url,
        )
        self._settings.sync()

        return normalized

    def get_api_key(
        self,
        base_url: str,
    ) -> str | None:
        """Return the API key stored for one OpenWebUI instance."""

        normalized_url = normalize_openwebui_url(base_url)

        return self._credential_store.get_secret(credential_target_for_url(normalized_url))

    def has_api_key(
        self,
        base_url: str,
    ) -> bool:
        """Return whether a non-blank API key exists for the server."""

        if not base_url.strip():
            return False

        secret = self.get_api_key(base_url)

        return bool(secret and secret.strip())

    def save_api_key(
        self,
        *,
        base_url: str,
        api_key: str,
    ) -> None:
        """Securely store the API key for one OpenWebUI instance."""

        normalized_url = normalize_openwebui_url(base_url)
        cleaned_key = api_key.strip()

        if not cleaned_key:
            raise ValueError("OpenWebUI API key is required.")

        self._credential_store.set_secret(
            credential_target_for_url(normalized_url),
            cleaned_key,
        )

    def delete_api_key(
        self,
        base_url: str,
    ) -> None:
        """Delete a stored key for one OpenWebUI instance."""

        normalized_url = normalize_openwebui_url(base_url)

        self._credential_store.delete_secret(credential_target_for_url(normalized_url))

    def _read_string(
        self,
        key: str,
        default: str,
    ) -> str:
        value = self._settings.value(
            key,
            default,
            type=str,
        )

        return value if value is not None else default

    def _read_bool(
        self,
        key: str,
        default: bool,
    ) -> bool:
        value = self._settings.value(
            key,
            default,
        )

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }


def normalize_openwebui_url(
    value: str,
) -> str:
    """Return a validated base URL suitable for OpenWebUI API calls."""

    cleaned = value.strip()

    if not cleaned:
        raise ValueError("OpenWebUI address is required.")

    if "://" not in cleaned:
        cleaned = f"http://{cleaned}"

    parsed = urlsplit(cleaned)

    if parsed.scheme.lower() not in {
        "http",
        "https",
    }:
        raise ValueError("OpenWebUI address must use http or https.")

    if not parsed.hostname:
        raise ValueError("OpenWebUI address must include a valid host name or IP address.")

    if parsed.username or parsed.password:
        raise ValueError("Do not include a username or password in the OpenWebUI address.")

    if parsed.query or parsed.fragment:
        raise ValueError("OpenWebUI address cannot include a query string or fragment.")

    path = parsed.path.rstrip("/")

    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc,
            path,
            "",
            "",
        )
    )


def credential_target_for_url(
    base_url: str,
) -> str:
    """Return a stable, non-secret Windows credential target."""

    normalized = normalize_openwebui_url(base_url)

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]

    return f"{_CREDENTIAL_PREFIX}/{digest}"
