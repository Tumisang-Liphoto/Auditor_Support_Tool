"""Primary application window and page routing."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from auditor_support_tool.core.constants import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MINIMUM_WINDOW_HEIGHT,
    MINIMUM_WINDOW_WIDTH,
)
from auditor_support_tool.gui.pages.dashboard_page import DashboardPage
from auditor_support_tool.gui.pages.placeholder_page import PlaceholderPage
from auditor_support_tool.gui.widgets.sidebar import Sidebar

PageDefinition = tuple[str, str, str]


class MainWindow(QMainWindow):
    """Main window for the Auditor Support Tool."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(
            MINIMUM_WINDOW_WIDTH,
            MINIMUM_WINDOW_HEIGHT,
        )

        self._pages: dict[str, QWidget] = {}
        self._page_titles: dict[str, str] = {}

        self._build_interface()
        self.show_route("dashboard")

    def _build_interface(self) -> None:
        central_widget = QWidget(self)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar = Sidebar()
        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("pageStack")

        self._sidebar.route_selected.connect(self.show_route)

        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(self._page_stack, 1)

        self.setCentralWidget(central_widget)

        self._register_pages()

    def _register_pages(self) -> None:
        dashboard = DashboardPage()
        dashboard.route_requested.connect(self.show_route)

        self._register_page(
            route="dashboard",
            title="Dashboard",
            page=dashboard,
        )

        page_definitions: tuple[PageDefinition, ...] = (
            (
                "engagements.all",
                "All Engagements",
                "Search, open and manage active audit engagements.",
            ),
            (
                "engagements.new",
                "New Engagement",
                "Create an engagement and intentionally select its audit domain and audit area.",
            ),
            (
                "engagements.archived",
                "Archived Engagements",
                "View and restore engagements that are no longer active.",
            ),
            (
                "workspace.overview",
                "Engagement Overview",
                "Review the current engagement, workflow status and "
                "outstanding analysis activities.",
            ),
            (
                "workspace.data_sources",
                "Data Sources",
                "Register Excel and CSV source files and verify file integrity.",
            ),
            (
                "workspace.data_profile",
                "Data Profile",
                "Review population statistics, detected fields and data-quality issues.",
            ),
            (
                "workspace.field_mapping",
                "Field Mapping",
                "Map auditee-specific source columns to standard audit fields.",
            ),
            (
                "workspace.audit_procedures",
                "Audit Procedures",
                "Select and configure procedures available for the engagement's audit domain.",
            ),
            (
                "workspace.results",
                "Results",
                "Review procedure results and combined transaction risk.",
            ),
            (
                "workspace.investigation",
                "Investigation",
                "Select records for follow-up, add notes and assign preliminary statuses.",
            ),
            (
                "reports.generate",
                "Generate Reports",
                "Generate audit working papers and structured exception reports.",
            ),
            (
                "reports.export",
                "Export Results",
                "Export full results or selected investigation records.",
            ),
            (
                "reports.previous",
                "Previous Reports",
                "Open reports previously generated for an engagement.",
            ),
            (
                "settings.user_profile",
                "User Profile",
                "Manage the local auditor profile and default information.",
            ),
            (
                "settings.appearance",
                "Appearance",
                "Select the application theme and display preferences.",
            ),
            (
                "settings.data_storage",
                "Data & Storage",
                "Review application paths, engagement locations and temporary-storage usage.",
            ),
            (
                "settings.ai_browser",
                "AI Browser Access",
                "Configure the approved browser-based local AI service.",
            ),
            (
                "settings.updates",
                "Updates",
                "Check GitHub Releases and review available improvements and corrections.",
            ),
            (
                "settings.backup_restore",
                "Backup & Restore",
                "Create and restore engagement or application-managed backups.",
            ),
            (
                "settings.reset",
                "Reset Application",
                "Reset settings, clear temporary data or perform a factory reset.",
            ),
            (
                "settings.diagnostics",
                "Diagnostics",
                "Review application version, environment, paths and "
                "non-sensitive diagnostic information.",
            ),
        )

        for route, title, description in page_definitions:
            self._register_page(
                route=route,
                title=title,
                page=PlaceholderPage(
                    title=title,
                    description=description,
                ),
            )

    def _register_page(
        self,
        route: str,
        title: str,
        page: QWidget,
    ) -> None:
        self._pages[route] = page
        self._page_titles[route] = title
        self._page_stack.addWidget(page)

    def show_route(self, route: str) -> None:
        """Display the page registered for a route."""

        page = self._pages.get(route)

        if page is None:
            self.statusBar().showMessage(f"Unknown page: {route}   |   Version {APP_VERSION}")
            return

        self._page_stack.setCurrentWidget(page)
        self._sidebar.set_active_route(route)

        title = self._page_titles[route]
        self.statusBar().showMessage(f"{title}   |   Ready   |   Version {APP_VERSION}")
