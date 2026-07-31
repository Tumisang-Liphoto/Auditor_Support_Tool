"""Application startup and lifecycle."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from auditor_support_tool.core.constants import (
    APP_NAME,
    APP_VERSION,
    ORGANIZATION_DOMAIN,
    ORGANIZATION_NAME,
)
from auditor_support_tool.core.paths import ensure_application_paths
from auditor_support_tool.gui.main_window import MainWindow
from auditor_support_tool.services.settings_service import SettingsService
from auditor_support_tool.services.theme_service import ThemeService
from auditor_support_tool.services.update_service import UpdateService


def _parse_startup_arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--update-health-marker")
    parser.add_argument("--update-health-token")
    parsed, _unknown = parser.parse_known_args(arguments[1:])
    return parsed


def _write_health_marker(marker_path: str | None, token: str | None) -> None:
    if not marker_path or not token:
        return
    marker = Path(marker_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(token, encoding="utf-8")


def main() -> int:
    """Start the Auditor Support Tool."""

    startup = _parse_startup_arguments(sys.argv)
    paths = ensure_application_paths()

    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setOrganizationDomain(ORGANIZATION_DOMAIN)
    application.setStyle("Fusion")

    settings_service = SettingsService(paths.config / "settings.ini")
    theme_service = ThemeService(application, settings_service)
    theme_service.apply_saved_appearance()

    update_service = UpdateService(
        current_version=APP_VERSION,
        paths=paths,
    )

    window = MainWindow(
        settings_service=settings_service,
        theme_service=theme_service,
        update_service=update_service,
    )
    window.show()

    QTimer.singleShot(
        1000,
        lambda: _write_health_marker(
            startup.update_health_marker,
            startup.update_health_token,
        ),
    )

    return application.exec()
