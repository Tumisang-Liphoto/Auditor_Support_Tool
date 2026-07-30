"""Persistent per-user application settings."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Locally stored auditor profile."""

    display_name: str = ""
    organization: str = ""
    role: str = "Auditor"
    default_currency: str = "LSL"


@dataclass(frozen=True, slots=True)
class AppearanceSettings:
    """Locally stored appearance preferences."""

    theme: str = "mint_green"
    mode: str = "light"


class SettingsService:
    """Read and write persistent application settings."""

    def __init__(self, settings_file: Path) -> None:
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        self._settings = QSettings(
            str(settings_file),
            QSettings.Format.IniFormat,
        )

    @property
    def file_path(self) -> Path:
        """Return the physical settings-file location."""

        return Path(self._settings.fileName())

    def get_user_profile(self) -> UserProfile:
        """Return the locally stored user profile."""

        return UserProfile(
            display_name=self._read_string(
                "profile/display_name",
                "",
            ),
            organization=self._read_string(
                "profile/organization",
                "",
            ),
            role=self._read_string(
                "profile/role",
                "Auditor",
            ),
            default_currency=self._read_string(
                "profile/default_currency",
                "LSL",
            ),
        )

    def save_user_profile(self, profile: UserProfile) -> None:
        """Save the local user profile."""

        self._settings.setValue(
            "profile/display_name",
            profile.display_name.strip(),
        )
        self._settings.setValue(
            "profile/organization",
            profile.organization.strip(),
        )
        self._settings.setValue(
            "profile/role",
            profile.role.strip() or "Auditor",
        )
        self._settings.setValue(
            "profile/default_currency",
            profile.default_currency.strip().upper() or "LSL",
        )

        self._settings.sync()

    def is_profile_complete(self) -> bool:
        """Return whether the minimum user profile has been completed."""

        profile = self.get_user_profile()

        return bool(profile.display_name.strip() and profile.organization.strip())

    def get_appearance(self) -> AppearanceSettings:
        """Return the stored theme and appearance mode."""

        return AppearanceSettings(
            theme=self._read_string(
                "appearance/theme",
                "mint_green",
            ),
            mode=self._read_string(
                "appearance/mode",
                "light",
            ),
        )

    def save_appearance(
        self,
        appearance: AppearanceSettings,
    ) -> None:
        """Save the selected theme and appearance mode."""

        self._settings.setValue(
            "appearance/theme",
            appearance.theme,
        )
        self._settings.setValue(
            "appearance/mode",
            appearance.mode,
        )

        self._settings.sync()

    def get_update_channel(self) -> str:
        """Return the selected application-update channel."""

        return self._read_string(
            "updates/channel",
            "testing",
        )

    def save_update_channel(self, channel: str) -> None:
        """Save the application-update channel."""

        normalized_channel = channel.strip().lower()

        if normalized_channel not in {"testing", "stable"}:
            raise ValueError("Update channel must be 'testing' or 'stable'.")

        self._settings.setValue(
            "updates/channel",
            normalized_channel,
        )
        self._settings.sync()

    def reset_all_settings(self) -> None:
        """Remove all application preferences from the settings file."""

        self._settings.clear()
        self._settings.sync()

    def sync(self) -> None:
        """Write pending settings changes to disk."""

        self._settings.sync()

    def _read_string(
        self,
        key: str,
        default: str,
    ) -> str:
        """Read a setting and return it as a string."""

        value = self._settings.value(
            key,
            default,
            type=str,
        )

        return value if value is not None else default
