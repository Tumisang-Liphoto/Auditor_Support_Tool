"""Tests for persistent OpenWebUI configuration and credential separation."""

from __future__ import annotations

from pathlib import Path

import pytest

from auditor_support_tool.services.openwebui_settings_service import (
    OpenWebUISettings,
    OpenWebUISettingsService,
    credential_target_for_url,
    normalize_openwebui_url,
)


class MemoryCredentialStore:
    """In-memory credential vault for unit tests."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get_secret(
        self,
        target: str,
    ) -> str | None:
        return self.values.get(target)

    def set_secret(
        self,
        target: str,
        secret: str,
    ) -> None:
        self.values[target] = secret

    def delete_secret(
        self,
        target: str,
    ) -> None:
        self.values.pop(
            target,
            None,
        )


def _service(
    tmp_path: Path,
) -> tuple[
    OpenWebUISettingsService,
    MemoryCredentialStore,
    Path,
]:
    settings_file = tmp_path / "settings.ini"
    credential_store = MemoryCredentialStore()

    service = OpenWebUISettingsService(
        settings_file=settings_file,
        credential_store=credential_store,
    )

    return (
        service,
        credential_store,
        settings_file,
    )


def test_openwebui_settings_round_trip(
    tmp_path: Path,
) -> None:
    service, _, _ = _service(tmp_path)

    saved = service.save_settings(
        OpenWebUISettings(
            enabled=True,
            base_url="192.168.8.2:3000/",
        )
    )

    assert saved == OpenWebUISettings(
        enabled=True,
        base_url="http://192.168.8.2:3000",
    )

    reloaded = service.get_settings()

    assert reloaded == saved


def test_enabled_openwebui_requires_address(
    tmp_path: Path,
) -> None:
    service, _, _ = _service(tmp_path)

    with pytest.raises(
        ValueError,
        match="address",
    ):
        service.save_settings(
            OpenWebUISettings(
                enabled=True,
                base_url="",
            )
        )


def test_api_key_is_not_written_to_settings_file(
    tmp_path: Path,
) -> None:
    service, _, settings_file = _service(tmp_path)

    base_url = "http://internal-ai:3000"
    secret = "sk-example-secret"

    service.save_settings(
        OpenWebUISettings(
            enabled=True,
            base_url=base_url,
        )
    )
    service.save_api_key(
        base_url=base_url,
        api_key=secret,
    )

    assert service.get_api_key(base_url) == secret

    settings_text = settings_file.read_text(encoding="utf-8")

    assert secret not in settings_text
    assert "api_key" not in settings_text.lower()


def test_credentials_are_isolated_by_openwebui_address(
    tmp_path: Path,
) -> None:
    service, _, _ = _service(tmp_path)

    first = "http://server-one:3000"
    second = "http://server-two:3000"

    service.save_api_key(
        base_url=first,
        api_key="first-key",
    )
    service.save_api_key(
        base_url=second,
        api_key="second-key",
    )

    assert service.get_api_key(first) == "first-key"
    assert service.get_api_key(second) == "second-key"


def test_delete_api_key_removes_only_selected_server(
    tmp_path: Path,
) -> None:
    service, _, _ = _service(tmp_path)

    first = "http://server-one:3000"
    second = "http://server-two:3000"

    service.save_api_key(
        base_url=first,
        api_key="first-key",
    )
    service.save_api_key(
        base_url=second,
        api_key="second-key",
    )

    service.delete_api_key(first)

    assert service.get_api_key(first) is None
    assert service.get_api_key(second) == "second-key"


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (
            "openwebui.local:3000/",
            "http://openwebui.local:3000",
        ),
        (
            " HTTPS://AI.INTERNAL/ ",
            "https://AI.INTERNAL",
        ),
        (
            "https://ai.internal/openwebui/",
            "https://ai.internal/openwebui",
        ),
    ),
)
def test_url_normalisation(
    raw: str,
    expected: str,
) -> None:
    assert normalize_openwebui_url(raw) == expected


def test_url_rejects_embedded_credentials() -> None:
    with pytest.raises(
        ValueError,
        match="username or password",
    ):
        normalize_openwebui_url("http://user:password@server:3000")


def test_credential_target_does_not_reveal_api_key() -> None:
    target = credential_target_for_url("http://internal-ai:3000")

    assert target.startswith("Auditor Support Tool/OpenWebUI/API Key/")
    assert len(target.rsplit("/", 1)[-1]) == 24
