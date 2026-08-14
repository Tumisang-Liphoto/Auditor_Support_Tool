"""Per-user application storage locations."""

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

    workspaces: Path
    workspace_backups: Path
    workspace_recovery: Path

    backups: Path
    updates: Path
    update_downloads: Path
    update_staging: Path
    update_runtime: Path
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

    workspaces_path = data_path / "Workspaces"
    workspace_backups_path = data_path / "Backups" / "Workspaces"
    workspace_recovery_path = data_path / "Recovery"

    updates_path = cache_path / "Updates"

    return ApplicationPaths(
        data=data_path,
        config=config_path,
        cache=cache_path,
        logs=log_path,
        workspaces=workspaces_path,
        workspace_backups=workspace_backups_path,
        workspace_recovery=workspace_recovery_path,
        backups=data_path / "Backups" / "Application",
        updates=updates_path,
        update_downloads=updates_path / "Downloads",
        update_staging=updates_path / "Staging",
        update_runtime=updates_path / "Runtime",
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
        paths.workspaces,
        paths.workspace_backups,
        paths.workspace_recovery,
        paths.backups,
        paths.updates,
        paths.update_downloads,
        paths.update_staging,
        paths.update_runtime,
        paths.temporary,
    ):
        path.mkdir(parents=True, exist_ok=True)

    return paths
