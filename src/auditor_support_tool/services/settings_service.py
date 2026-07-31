"""Persistent per-user application settings."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings

SUPPORTED_APPEARANCE_THEMES = {
    "mint_green",
    "auditor_blue",
    "professional_teal",
    "royal_purple",
    "graphite",
}

SUPPORTED_APPEARANCE_MODES = {
    "system",
    "light",
    "dark",
}


@dataclass(frozen=True, slots=True)
class UserProfile:
    """Locally stored auditor profile."""

    preferred_name: str = ""
    full_name: str = ""
    job_title: str = "Auditor"
    organization: str = ""
    directorate: str = ""
    email_address: str = ""
    phone_number: str = ""
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
        """Return the locally stored user profile.

        Older display-name and role settings are retained as migration
        fallbacks so existing profiles continue to work after an update.
        """

        legacy_display_name = self._read_string(
            "profile/display_name",
            "",
        )

        full_name = self._read_string(
            "profile/full_name",
            legacy_display_name,
        )

        preferred_name = self._read_string(
            "profile/preferred_name",
            self._derive_preferred_name(full_name),
        )

        legacy_role = self._read_string(
            "profile/role",
            "Auditor",
        )

        return UserProfile(
            preferred_name=preferred_name,
            full_name=full_name,
            job_title=self._read_string(
                "profile/job_title",
                legacy_role,
            ),
            organization=self._read_string(
                "profile/organization",
                "",
            ),
            directorate=self._read_string(
                "profile/directorate",
                "",
            ),
            email_address=self._read_string(
                "profile/email_address",
                "",
            ),
            phone_number=self._read_string(
                "profile/phone_number",
                "",
            ),
            default_currency=self._read_string(
                "profile/default_currency",
                "LSL",
            ),
        )

    def save_user_profile(self, profile: UserProfile) -> None:
        """Save the local user profile."""

        preferred_name = profile.preferred_name.strip()
        full_name = profile.full_name.strip()
        job_title = profile.job_title.strip()
        organization = profile.organization.strip()
        directorate = profile.directorate.strip()
        email_address = profile.email_address.strip().lower()
        phone_number = profile.phone_number.strip()
        default_currency = profile.default_currency.strip().upper() or "LSL"

        self._settings.setValue(
            "profile/preferred_name",
            preferred_name,
        )
        self._settings.setValue(
            "profile/full_name",
            full_name,
        )
        self._settings.setValue(
            "profile/job_title",
            job_title,
        )
        self._settings.setValue(
            "profile/organization",
            organization,
        )
        self._settings.setValue(
            "profile/directorate",
            directorate,
        )
        self._settings.setValue(
            "profile/email_address",
            email_address,
        )
        self._settings.setValue(
            "profile/phone_number",
            phone_number,
        )
        self._settings.setValue(
            "profile/default_currency",
            default_currency,
        )

        # Preserve compatibility with an earlier application version.
        self._settings.setValue(
            "profile/display_name",
            full_name,
        )
        self._settings.setValue(
            "profile/role",
            job_title,
        )

        self._settings.sync()

    def is_profile_complete(self) -> bool:
        """Return whether all mandatory profile fields are complete."""

        profile = self.get_user_profile()

        return bool(
            profile.preferred_name.strip()
            and profile.full_name.strip()
            and profile.job_title.strip()
            and profile.organization.strip()
        )

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
        """Validate and save the selected appearance."""

        theme = appearance.theme.strip().lower()
        mode = appearance.mode.strip().lower()

        if theme not in SUPPORTED_APPEARANCE_THEMES:
            raise ValueError(f"Unsupported application theme: {appearance.theme}")

        if mode not in SUPPORTED_APPEARANCE_MODES:
            raise ValueError("Appearance mode must be 'system', 'light' or 'dark'.")

        self._settings.setValue(
            "appearance/theme",
            theme,
        )
        self._settings.setValue(
            "appearance/mode",
            mode,
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

    @staticmethod
    def _derive_preferred_name(full_name: str) -> str:
        """Derive a preferred name from an older saved full name."""

        parts = full_name.strip().split()

        return parts[0] if parts else ""
