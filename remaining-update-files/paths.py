"""Application storage locations.

All runtime data is stored in locations writable by the current Windows user.
The application must not require administrator rights to create or update these
folders.
"""

from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs

from auditor_support_tool.core.constants import APP_NAME


@dataclass(frozen=True, slots=True)
class ApplicationPaths:
    """Resolved application-managed storage locations."""

    data: Path
    config: Path
    cache: Path
    logs: Path
    backups: Path
    updates: Path
    temporary: Path


def get_application_paths() -> ApplicationPaths:
    """Return the standard per-user storage locations."""

    directories = PlatformDirs(
        appname=APP_NAME,
        appauthor=False,
        roaming=False,
    )

    data_path = Path(directories.user_data_dir)
    config_path = Path(directories.user_config_dir)
    cache_path = Path(directories.user_cache_dir)
    log_path = Path(directories.user_log_dir)

    return ApplicationPaths(
        data=data_path,
        config=config_path,
        cache=cache_path,
        logs=log_path,
        backups=data_path / "Backups",
        updates=cache_path / "Updates",
        temporary=cache_path / "Temporary",
    )


def ensure_application_paths() -> ApplicationPaths:
    """Create the application-managed folders where they do not exist."""

    paths = get_application_paths()

    for path in (
        paths.data,
        paths.config,
        paths.cache,
        paths.logs,
        paths.backups,
        paths.updates,
        paths.temporary,
    ):
        path.mkdir(parents=True, exist_ok=True)

    return paths
