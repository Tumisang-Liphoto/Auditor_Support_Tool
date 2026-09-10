"""Tests for persistent OpenWebUI default-model selection."""

from pathlib import Path

from auditor_support_tool.services.openwebui_settings_service import (
    OpenWebUISettings,
    OpenWebUISettingsService,
)


class MemoryCredentialStore:
    def get_secret(self, target: str) -> str | None:
        del target
        return None

    def set_secret(self, target: str, secret: str) -> None:
        del target, secret

    def delete_secret(self, target: str) -> None:
        del target


def test_default_model_round_trip(
    tmp_path: Path,
) -> None:
    service = OpenWebUISettingsService(
        settings_file=tmp_path / "settings.ini",
        credential_store=MemoryCredentialStore(),
    )

    saved = service.save_settings(
        OpenWebUISettings(
            enabled=True,
            base_url="http://ai:3000",
            default_model="qwen-audit",
        )
    )

    assert saved.default_model == "qwen-audit"
    assert service.get_settings().default_model == "qwen-audit"
