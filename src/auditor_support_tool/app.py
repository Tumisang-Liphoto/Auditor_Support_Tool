"""Application startup and lifecycle."""

import sys

from PySide6.QtWidgets import QApplication

from auditor_support_tool.core.constants import (
    APP_NAME,
    APP_VERSION,
    ORGANIZATION_DOMAIN,
    ORGANIZATION_NAME,
)
from auditor_support_tool.core.paths import ensure_application_paths
from auditor_support_tool.gui.main_window import MainWindow
from auditor_support_tool.services.theme_service import build_default_stylesheet


def main() -> int:
    """Start the Auditor Support Tool."""

    ensure_application_paths()

    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setOrganizationDomain(ORGANIZATION_DOMAIN)
    application.setStyle("Fusion")
    application.setStyleSheet(build_default_stylesheet())

    window = MainWindow()
    window.show()

    return application.exec()
