"""Tests for the shared technician-password settings lock."""

from __future__ import annotations

from auditor_support_tool.services.administrator_settings_service import (
    AdministratorSettingsService,
    derive_password_verifier,
)

_TEST_PASSWORD = "Technician-Test-Password"
_TEST_SALT = bytes.fromhex("00112233445566778899aabbccddeeff")
_TEST_VERIFIER = derive_password_verifier(_TEST_PASSWORD, _TEST_SALT)


def _service() -> AdministratorSettingsService:
    return AdministratorSettingsService(
        salt=_TEST_SALT,
        verifier=_TEST_VERIFIER,
    )


def test_shared_password_unlocks_multiple_installation_instances() -> None:
    first = _service()
    second = _service()

    assert first.unlock(_TEST_PASSWORD).success is True
    assert second.unlock(_TEST_PASSWORD).success is True
    assert first.is_unlocked is True
    assert second.is_unlocked is True


def test_wrong_password_does_not_unlock() -> None:
    service = _service()

    result = service.unlock("wrong-password")

    assert result.success is False
    assert "incorrect" in result.message.lower()
    assert service.is_unlocked is False


def test_lock_clears_session_unlock_state() -> None:
    service = _service()
    service.unlock(_TEST_PASSWORD)

    service.lock()

    assert service.is_unlocked is False


def test_unlock_state_is_not_shared_between_service_instances() -> None:
    first = _service()
    second = _service()

    first.unlock(_TEST_PASSWORD)

    assert first.is_unlocked is True
    assert second.is_unlocked is False


def test_unconfigured_build_cannot_be_unlocked() -> None:
    service = AdministratorSettingsService(
        salt=b"",
        verifier=b"",
    )

    result = service.unlock(_TEST_PASSWORD)

    assert service.is_configured is False
    assert result.success is False
    assert "not configured" in result.message.lower()


def test_lock_state_signal_reports_unlock_and_lock() -> None:
    service = _service()
    states: list[bool] = []
    service.lock_state_changed.connect(states.append)

    service.unlock(_TEST_PASSWORD)
    service.lock()

    assert states == [True, False]
