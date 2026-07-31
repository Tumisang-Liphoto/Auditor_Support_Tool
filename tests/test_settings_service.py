"""Tests for persistent application settings."""

from PySide6.QtCore import QSettings

from auditor_support_tool.services.settings_service import (
    AppearanceSettings,
    SettingsService,
    UserProfile,
)


def test_user_profile_round_trip(tmp_path) -> None:
    """A complete profile should persist across service instances."""

    settings_file = tmp_path / "settings.ini"
    service = SettingsService(settings_file)

    expected_profile = UserProfile(
        preferred_name="Example",
        full_name="Example Auditor",
        job_title="Senior Auditor",
        organization="Example Audit Office",
        directorate="Financial Audit",
        email_address="example.auditor@example.org",
        phone_number="+266 5000 0000",
        default_currency="LSL",
    )

    service.save_user_profile(expected_profile)

    reloaded_service = SettingsService(settings_file)

    assert reloaded_service.get_user_profile() == expected_profile
    assert reloaded_service.is_profile_complete() is True


def test_legacy_profile_is_migrated(tmp_path) -> None:
    """Older display-name and role settings should remain usable."""

    settings_file = tmp_path / "settings.ini"

    legacy_settings = QSettings(
        str(settings_file),
        QSettings.Format.IniFormat,
    )
    legacy_settings.setValue(
        "profile/display_name",
        "Example Auditor",
    )
    legacy_settings.setValue(
        "profile/organization",
        "Example Audit Office",
    )
    legacy_settings.setValue(
        "profile/role",
        "Audit Manager",
    )
    legacy_settings.sync()

    service = SettingsService(settings_file)
    profile = service.get_user_profile()

    assert profile.preferred_name == "Example"
    assert profile.full_name == "Example Auditor"
    assert profile.job_title == "Audit Manager"
    assert profile.organization == "Example Audit Office"
    assert service.is_profile_complete() is True


def test_incomplete_profile_is_detected(tmp_path) -> None:
    """Missing mandatory information should keep the profile incomplete."""

    service = SettingsService(tmp_path / "settings.ini")

    service.save_user_profile(
        UserProfile(
            preferred_name="Example",
            full_name="Example Auditor",
            job_title="",
            organization="Example Audit Office",
        )
    )

    assert service.is_profile_complete() is False


def test_appearance_round_trip(tmp_path) -> None:
    """Appearance preferences should persist."""

    settings_file = tmp_path / "settings.ini"
    service = SettingsService(settings_file)

    expected_appearance = AppearanceSettings(
        theme="mint_green",
        mode="dark",
    )

    service.save_appearance(expected_appearance)

    reloaded_service = SettingsService(settings_file)

    assert reloaded_service.get_appearance() == expected_appearance


def test_update_channel_validation(tmp_path) -> None:
    """Testing and stable should be accepted as update channels."""

    service = SettingsService(tmp_path / "settings.ini")

    service.save_update_channel("stable")

    assert service.get_update_channel() == "stable"


def test_reset_all_settings(tmp_path) -> None:
    """Resetting settings should restore the defined defaults."""

    settings_file = tmp_path / "settings.ini"
    service = SettingsService(settings_file)

    service.save_user_profile(
        UserProfile(
            preferred_name="Example",
            full_name="Example Auditor",
            job_title="Auditor",
            organization="Example Audit Office",
        )
    )
    service.save_appearance(
        AppearanceSettings(
            theme="mint_green",
            mode="dark",
        )
    )

    service.reset_all_settings()

    assert service.get_user_profile() == UserProfile()
    assert service.get_appearance() == AppearanceSettings()
    assert service.get_update_channel() == "testing"
