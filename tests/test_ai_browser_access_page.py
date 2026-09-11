"""Tests for administrator protection on the AI Integration settings page."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from auditor_support_tool.gui.pages import ai_browser_access_page as ai_page_module
from auditor_support_tool.gui.pages.ai_browser_access_page import AIBrowserAccessPage
from auditor_support_tool.services.administrator_settings_service import (
    AdministratorSettingsService,
    derive_password_verifier,
)
from auditor_support_tool.services.openwebui_settings_service import (
    OpenWebUISettings,
    OpenWebUISettingsService,
)

_TEST_PASSWORD = "Technician-Test-Password"
_TEST_SALT = bytes.fromhex("00112233445566778899aabbccddeeff")
_TEST_VERIFIER = derive_password_verifier(_TEST_PASSWORD, _TEST_SALT)


class MemoryCredentialStore:
    """In-memory credential vault used by the AI settings page tests."""

    values: dict[str, str]

    def __init__(self) -> None:
        self.values = {}

    def get_secret(self, target: str) -> str | None:
        return self.values.get(target)

    def set_secret(self, target: str, secret: str) -> None:
        self.values[target] = secret

    def delete_secret(self, target: str) -> None:
        self.values.pop(target, None)


def _application() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def _administrator_service() -> AdministratorSettingsService:
    return AdministratorSettingsService(
        salt=_TEST_SALT,
        verifier=_TEST_VERIFIER,
    )


def _page(
    tmp_path: Path,
    monkeypatch,
    *,
    enabled: bool = True,
    base_url: str = "http://approved-ai:3000",
) -> tuple[AIBrowserAccessPage, AdministratorSettingsService, MemoryCredentialStore]:
    _application()

    credential_store = MemoryCredentialStore()
    monkeypatch.setattr(
        ai_page_module,
        "WindowsCredentialService",
        lambda: credential_store,
    )

    settings_file = tmp_path / "settings.ini"
    OpenWebUISettingsService(
        settings_file=settings_file,
        credential_store=credential_store,
    ).save_settings(
        OpenWebUISettings(
            enabled=enabled,
            base_url=base_url,
        )
    )

    administrator_service = _administrator_service()
    page = AIBrowserAccessPage(
        settings_file=settings_file,
        administrator_settings_service=administrator_service,
    )

    return page, administrator_service, credential_store


def test_protected_ai_controls_are_locked_by_default(tmp_path: Path, monkeypatch) -> None:
    page, administrator_service, _ = _page(tmp_path, monkeypatch)

    assert administrator_service.is_unlocked is False
    assert page._enabled_input.isEnabled() is False
    assert page._base_url_input.isReadOnly() is True
    assert page._api_key_input.isEnabled() is False
    assert page._save_button.isEnabled() is False
    assert page._remove_key_button.isEnabled() is False
    assert page._test_button.isEnabled() is True
    assert page._open_button.isEnabled() is True
    assert page._administrator_button.text() == "Unlock Settings"


def test_unlock_enables_protected_ai_controls(tmp_path: Path, monkeypatch) -> None:
    page, administrator_service, _ = _page(tmp_path, monkeypatch)

    result = administrator_service.unlock(_TEST_PASSWORD)

    assert result.success is True
    assert page._enabled_input.isEnabled() is True
    assert page._base_url_input.isReadOnly() is False
    assert page._api_key_input.isEnabled() is True
    assert page._save_button.isEnabled() is True
    assert page._administrator_button.text() == "Lock Settings"


def test_lock_button_discards_unsaved_protected_edits(tmp_path: Path, monkeypatch) -> None:
    page, administrator_service, _ = _page(tmp_path, monkeypatch)
    administrator_service.unlock(_TEST_PASSWORD)
    page._base_url_input.setText("http://unsaved-ai:3000")
    page._enabled_input.setChecked(False)

    page._toggle_administrator_lock()

    assert administrator_service.is_unlocked is False
    assert page._base_url_input.text() == "http://approved-ai:3000"
    assert page._enabled_input.isChecked() is True
    assert page._base_url_input.isReadOnly() is True


def test_saved_api_key_can_be_used_but_not_removed_while_locked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    page, administrator_service, credential_store = _page(tmp_path, monkeypatch)
    administrator_service.unlock(_TEST_PASSWORD)
    page._settings_service.save_api_key(
        base_url="http://approved-ai:3000",
        api_key="secret-api-key",
    )
    page._refresh_credential_status()

    assert page._remove_key_button.isEnabled() is True

    page._toggle_administrator_lock()

    assert page._remove_key_button.isEnabled() is False
    assert credential_store.values


def test_unconfigured_build_keeps_unlock_action_disabled(tmp_path: Path, monkeypatch) -> None:
    _application()
    credential_store = MemoryCredentialStore()
    monkeypatch.setattr(
        ai_page_module,
        "WindowsCredentialService",
        lambda: credential_store,
    )
    administrator_service = AdministratorSettingsService(
        salt=b"",
        verifier=b"",
    )

    page = AIBrowserAccessPage(
        settings_file=tmp_path / "settings.ini",
        administrator_settings_service=administrator_service,
    )

    assert page._administrator_button.isEnabled() is False
    assert "not yet been configured" in page._administrator_status.text().lower()
