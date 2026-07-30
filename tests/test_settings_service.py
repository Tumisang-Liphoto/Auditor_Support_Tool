"""Tests for persistent application settings."""

from auditor_support_tool.services.settings_service import (
    AppearanceSettings,
    SettingsService,
    UserProfile,
)


def test_user_profile_round_trip(tmp_path) -> None:
    """A saved profile should be available from a new service instance."""

    settings_file = tmp_path / "settings.ini"

    service = SettingsService(settings_file)

    expected_profile = UserProfile(
        display_name="Tumisang Liphoto",
        organization="Office of the Auditor-General",
        role="Director ICT",
        default_currency="LSL",
    )

    service.save_user_profile(expected_profile)

    reloaded_service = SettingsService(settings_file)

    assert reloaded_service.get_user_profile() == expected_profile
    assert reloaded_service.is_profile_complete() is True


def test_incomplete_profile_is_detected(tmp_path) -> None:
    """A profile without the required names should remain incomplete."""

    service = SettingsService(tmp_path / "settings.ini")

    service.save_user_profile(
        UserProfile(
            display_name="",
            organization="",
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
    """Only the testing and stable channels should be accepted."""

    service = SettingsService(tmp_path / "settings.ini")

    service.save_update_channel("stable")

    assert service.get_update_channel() == "stable"


def test_reset_all_settings(tmp_path) -> None:
    """Resetting settings should restore the defined defaults."""

    settings_file = tmp_path / "settings.ini"

    service = SettingsService(settings_file)

    service.save_user_profile(
        UserProfile(
            display_name="Example Auditor",
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
