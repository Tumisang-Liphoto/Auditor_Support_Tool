"""Primary application window and page routing."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
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
    GITHUB_REPOSITORY_NAME,
    GITHUB_REPOSITORY_OWNER,
    MINIMUM_WINDOW_HEIGHT,
    MINIMUM_WINDOW_WIDTH,
)
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.about_page import AboutPage
from auditor_support_tool.gui.pages.appearance_page import AppearancePage
from auditor_support_tool.gui.pages.dashboard_page import DashboardPage
from auditor_support_tool.gui.pages.data_sources_page import DataSourcesPage
from auditor_support_tool.gui.pages.manuals_page import ManualsPage
from auditor_support_tool.gui.pages.pdf_viewer_page import (
    PdfViewerPage,
)
from auditor_support_tool.gui.pages.placeholder_page import PlaceholderPage
from auditor_support_tool.gui.pages.test_description_page import (
    TestDescriptionPage,
)
from auditor_support_tool.gui.pages.updates_page import UpdatesPage
from auditor_support_tool.gui.pages.user_profile_page import (
    UserProfilePage,
)
from auditor_support_tool.gui.widgets.sidebar import Sidebar
from auditor_support_tool.services.settings_service import (
    SettingsService,
    UserProfile,
)
from auditor_support_tool.services.theme_service import ThemeService
from auditor_support_tool.services.update_service import UpdateService

PageDefinition = tuple[str, str, str]


class MainWindow(QMainWindow):
    """Main window for the Auditor Support Tool."""

    def __init__(
        self,
        settings_service: SettingsService,
        theme_service: ThemeService,
        update_service: UpdateService,
    ) -> None:
        super().__init__()

        self._settings_service = settings_service
        self._theme_service = theme_service
        self._update_service = update_service
        self._workspace_state = WorkspaceState(self)
        self._profile_required = not self._settings_service.is_profile_complete()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(
            DEFAULT_WINDOW_WIDTH,
            DEFAULT_WINDOW_HEIGHT,
        )
        self.setMinimumSize(
            MINIMUM_WINDOW_WIDTH,
            MINIMUM_WINDOW_HEIGHT,
        )

        self._pages: dict[str, QWidget] = {}
        self._page_titles: dict[str, str] = {}
        self._menu_actions: dict[str, QAction] = {}

        self._build_interface()

        if self._profile_required:
            self.show_route("settings.user_profile")
            self.statusBar().showMessage("Complete the local user profile to continue.")
        else:
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
        self._build_menu_bar()

    def _build_menu_bar(self) -> None:
        """Create the application menu bar and keyboard shortcuts."""

        menu_bar = self.menuBar()
        menu_bar.setObjectName("applicationMenuBar")

        file_menu = menu_bar.addMenu("&File")
        file_menu.setObjectName("applicationMenu")
        file_menu.addAction(
            self._create_route_action(
                key="dashboard",
                text="Dashboard",
                route="dashboard",
                shortcut="Ctrl+H",
                status_tip="Open the application dashboard.",
            )
        )
        file_menu.addSeparator()
        file_menu.addAction(
            self._create_route_action(
                key="new_engagement",
                text="New Engagement",
                route="engagements.new",
                shortcut="Ctrl+N",
                status_tip="Create a new audit engagement.",
            )
        )
        file_menu.addAction(
            self._create_route_action(
                key="open_engagement",
                text="Open Engagement",
                route="engagements.all",
                shortcut="Ctrl+O",
                status_tip="Open or manage an existing engagement.",
            )
        )
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.setStatusTip("Close the Auditor Support Tool.")
        exit_action.triggered.connect(self.close)
        self._menu_actions["exit"] = exit_action
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&View")
        view_menu.setObjectName("applicationMenu")
        view_menu.addAction(
            self._create_route_action(
                key="appearance",
                text="Appearance",
                route="settings.appearance",
                shortcut="Ctrl+,",
                status_tip="Change the application theme and appearance mode.",
            )
        )
        view_menu.addAction(
            self._create_route_action(
                key="data_storage",
                text="Data && Storage",
                route="settings.data_storage",
                status_tip="Review application data and storage locations.",
            )
        )
        view_menu.addAction(
            self._create_route_action(
                key="diagnostics",
                text="Diagnostics",
                route="settings.diagnostics",
                status_tip="Review application diagnostics.",
            )
        )

        help_menu = menu_bar.addMenu("&Help")
        help_menu.setObjectName("applicationMenu")
        help_menu.addAction(
            self._create_route_action(
                key="manuals",
                text="Manuals",
                route="about.manuals",
                shortcut="F1",
                status_tip="Open the application manuals.",
            )
        )
        help_menu.addAction(
            self._create_route_action(
                key="updates",
                text="Check for Updates",
                route="settings.updates",
                status_tip="Check GitHub Releases for application updates.",
            )
        )
        releases_action = QAction("View Releases", self)
        releases_action.setStatusTip("Open published GitHub releases.")
        releases_action.triggered.connect(self._open_release_page)
        self._menu_actions["view_releases"] = releases_action
        help_menu.addAction(releases_action)
        help_menu.addSeparator()
        help_menu.addAction(
            self._create_route_action(
                key="about",
                text="About Auditor Support Tool",
                route="about.overview",
                status_tip="View application information.",
            )
        )

    def _create_route_action(
        self,
        *,
        key: str,
        text: str,
        route: str,
        shortcut: str | None = None,
        status_tip: str = "",
    ) -> QAction:
        """Create a menu action that opens an existing application route."""

        action = QAction(text, self)

        if shortcut:
            action.setShortcut(QKeySequence(shortcut))

        if status_tip:
            action.setStatusTip(status_tip)

        action.triggered.connect(
            lambda checked=False, selected_route=route: self.show_route(selected_route)
        )
        self._menu_actions[key] = action

        return action

    @staticmethod
    def _repository_url() -> str:
        """Return the public GitHub repository URL."""

        return f"https://github.com/{GITHUB_REPOSITORY_OWNER}/{GITHUB_REPOSITORY_NAME}"

    def _open_release_page(self) -> None:
        """Open the GitHub Releases page in the default browser."""

        QDesktopServices.openUrl(QUrl(f"{self._repository_url()}/releases"))

    def _register_pages(self) -> None:
        dashboard = DashboardPage()
        dashboard.route_requested.connect(self.show_route)

        self._register_page(
            route="dashboard",
            title="Dashboard",
            page=dashboard,
        )

        appearance_page = AppearancePage(
            settings_service=self._settings_service,
            theme_service=self._theme_service,
        )

        self._register_page(
            route="settings.appearance",
            title="Appearance",
            page=appearance_page,
        )

        user_profile_page = UserProfilePage(
            settings_service=self._settings_service,
        )
        user_profile_page.profile_saved.connect(self._handle_profile_saved)

        self._register_page(
            route="settings.user_profile",
            title="User Profile",
            page=user_profile_page,
        )

        updates_page = UpdatesPage(
            settings_service=self._settings_service,
            update_service=self._update_service,
        )

        self._register_page(
            route="settings.updates",
            title="Updates",
            page=updates_page,
        )

        self._register_page(
            route="about.overview",
            title="About",
            page=AboutPage(),
        )

        manuals_page = ManualsPage()
        manuals_page.document_requested.connect(self._open_pdf_description)

        self._register_page(
            route="about.manuals",
            title="Manuals",
            page=manuals_page,
        )

        test_description_page = TestDescriptionPage()
        test_description_page.document_requested.connect(self._open_pdf_description)

        self._register_page(
            route="about.test_descriptions",
            title="Test Descriptions",
            page=test_description_page,
        )

        self._pdf_viewer_page = PdfViewerPage()
        self._pdf_viewer_page.back_requested.connect(self.show_route)

        self._register_page(
            route="about.pdf_viewer",
            title="PDF Viewer",
            page=self._pdf_viewer_page,
        )

        data_sources_page = DataSourcesPage(
            workspace_state=self._workspace_state,
        )

        self._register_page(
            route="workspace.data_sources",
            title="Data Sources",
            page=data_sources_page,
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
            if route in self._pages:
                continue

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

    def _open_pdf_description(
        self,
        path: str,
        title: str,
        subtitle: str,
        return_route: str,
    ) -> None:
        """Open a PDF using the user's saved viewing preference."""

        document_path = Path(path)

        if not document_path.is_file():
            self.statusBar().showMessage(
                f"PDF document not found: {document_path.name} | Version {APP_VERSION}"
            )
            return

        if not self._settings_service.get_open_pdfs_in_application():
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(document_path.resolve())))

            if opened:
                self.statusBar().showMessage(
                    f"Opened {title} in the default Windows PDF reader | Version {APP_VERSION}"
                )
            else:
                self.statusBar().showMessage(
                    f"Windows could not open {title} | Version {APP_VERSION}"
                )

            return

        loaded = self._pdf_viewer_page.open_document(
            path=document_path,
            title=title,
            subtitle=subtitle,
            return_route=return_route,
        )

        if loaded:
            self.show_route("about.pdf_viewer")
            return

        self.statusBar().showMessage(f"Unable to open PDF document | Version {APP_VERSION}")

    def show_route(self, route: str) -> None:
        """Display the page registered for a route."""

        current_page = self._page_stack.currentWidget()

        if current_page is self._pdf_viewer_page and route != "about.pdf_viewer":
            self._pdf_viewer_page.close_document()

        if self._profile_required and route != "settings.user_profile":
            route = "settings.user_profile"
            self.statusBar().showMessage("Complete the local user profile to continue.")

        page = self._pages.get(route)

        if page is None:
            self.statusBar().showMessage(f"Unknown page: {route}   |   Version {APP_VERSION}")
            return

        self._page_stack.setCurrentWidget(page)
        self._sidebar.set_active_route(route)

        title = self._page_titles[route]

        if self._profile_required:
            status = "Profile setup required"
        else:
            status = "Ready"

        self.statusBar().showMessage(f"{title}   |   {status}   |   Version {APP_VERSION}")

    def _handle_profile_saved(
        self,
        profile: UserProfile,
    ) -> None:
        """Unlock the application after first-run profile completion."""

        first_run_completed = self._profile_required
        self._profile_required = False

        profile_name = profile.preferred_name.strip() or profile.full_name.strip()

        if first_run_completed:
            self.statusBar().showMessage(
                f"Welcome, {profile_name}. Your local profile has been created."
            )
            self.show_route("dashboard")
            return

        self.statusBar().showMessage(f"Profile updated for {profile_name}.")
