"""Primary application window and page routing."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.application_procedure_bootstrap import (
    create_application_procedure_registry,
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
from auditor_support_tool.core.test_engine_models import TestEngineOutcome
from auditor_support_tool.core.workspace_readiness_service import (
    WorkspaceReadinessService,
    WorkspaceStage,
)
from auditor_support_tool.core.workspace_service import (
    WorkspaceService,
    WorkspaceServiceError,
    WorkspaceSourceIntegrityError,
)
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.dialogs.new_workspace_dialog import (
    NewWorkspaceDialog,
)
from auditor_support_tool.gui.pages.about_page import AboutPage
from auditor_support_tool.gui.pages.appearance_page import AppearancePage
from auditor_support_tool.gui.pages.audit_procedures_page import (
    AuditProceduresPage,
)
from auditor_support_tool.gui.pages.dashboard_page import DashboardPage
from auditor_support_tool.gui.pages.data_preparation_page import (
    DataPreparationPage,
)
from auditor_support_tool.gui.pages.data_profile_page import DataProfilePage
from auditor_support_tool.gui.pages.data_sources_page import DataSourcesPage
from auditor_support_tool.gui.pages.field_mapping_page import (
    FieldMappingPage,
)
from auditor_support_tool.gui.pages.manuals_page import ManualsPage
from auditor_support_tool.gui.pages.pdf_viewer_page import PdfViewerPage
from auditor_support_tool.gui.pages.placeholder_page import PlaceholderPage
from auditor_support_tool.gui.pages.results_page import ResultsPage
from auditor_support_tool.gui.pages.test_description_page import (
    TestDescriptionPage,
)
from auditor_support_tool.gui.pages.updates_page import UpdatesPage
from auditor_support_tool.gui.pages.user_profile_page import UserProfilePage
from auditor_support_tool.gui.widgets.breadcrumb_bar import (
    BreadcrumbBar,
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
        workspace_service: WorkspaceService,
    ) -> None:
        super().__init__()

        self._settings_service = settings_service
        self._theme_service = theme_service
        self._update_service = update_service
        self._workspace_service = workspace_service
        self._workspace_state = WorkspaceState(self)
        self._procedure_registry = create_application_procedure_registry()
        self._workspace_readiness_service = WorkspaceReadinessService()

        self._workspace_state.workspace_identity_changed.connect(self._update_window_title)
        self._workspace_state.workspace_dirty_changed.connect(self._update_window_title)
        self._workspace_state.workspace_file_changed.connect(self._update_window_title)

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

        self._readiness_warning_timer = QTimer(self)
        self._readiness_warning_timer.setSingleShot(True)
        self._readiness_warning_timer.timeout.connect(self._clear_readiness_warning)

        self._build_interface()

        if self._profile_required:
            self.show_route("settings.user_profile")
            self.statusBar().showMessage("Complete the local user profile to continue.")
        else:
            self.show_route("dashboard")

    def _update_window_title(self) -> None:
        """Update the title with the active workspace and save state."""

        identity = self._workspace_state.workspace_identity

        if identity is None:
            self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
            return

        unsaved_marker = "*" if self._workspace_state.is_dirty else ""

        self.setWindowTitle(f"{identity.name}{unsaved_marker} — {APP_NAME} {APP_VERSION}")

    def _build_interface(self) -> None:
        """Build the main application layout."""

        central_widget = QWidget(self)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar = Sidebar(
            workspace_state=self._workspace_state,
        )

        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("applicationTopBar")

        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 8, 12, 8)
        top_bar_layout.setSpacing(8)

        self._sidebar_toggle_button = QToolButton()
        self._sidebar_toggle_button.setObjectName("sidebarToggleButton")
        self._sidebar_toggle_button.setText("☰")
        self._sidebar_toggle_button.setToolTip("Hide or show the navigation panel")
        self._sidebar_toggle_button.setAccessibleName("Toggle navigation panel")
        self._sidebar_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sidebar_toggle_button.clicked.connect(self._toggle_sidebar)

        top_bar_layout.addWidget(self._sidebar_toggle_button)

        self._breadcrumb_bar = BreadcrumbBar()

        top_bar_layout.addWidget(
            self._breadcrumb_bar,
            1,
        )

        self._page_stack = QStackedWidget()
        self._page_stack.setObjectName("pageStack")

        content_layout.addWidget(top_bar)
        content_layout.addWidget(self._page_stack, 1)

        self._sidebar.route_selected.connect(self._handle_sidebar_selection)

        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(content_container, 1)

        self.setCentralWidget(central_widget)

        self._readiness_warning_label = QLabel()
        self._readiness_warning_label.setObjectName("readinessWarningLabel")
        self._readiness_warning_label.setStyleSheet(
            "QLabel#readinessWarningLabel { color: #d32f2f; font-weight: 700;}"
        )
        self._readiness_warning_label.setVisible(False)
        self.statusBar().addWidget(
            self._readiness_warning_label,
            1,
        )

        self._register_pages()
        self._build_menu_bar()

    def _handle_sidebar_selection(
        self,
        route: str,
    ) -> None:
        """Handle sidebar page routes and workspace actions."""

        if route == "workspace.new":
            self._create_new_workspace()
            return

        self.show_route(route)

    def _toggle_sidebar(self) -> None:
        """Hide or show the application navigation panel."""

        sidebar_will_be_visible = not self._sidebar.isVisible()
        self._sidebar.setVisible(sidebar_will_be_visible)

        tooltip = (
            "Hide the navigation panel" if sidebar_will_be_visible else "Show the navigation panel"
        )
        self._sidebar_toggle_button.setToolTip(tooltip)

    def _save_workspace(self) -> bool:
        """Save the active audit workspace."""

        if not self._workspace_state.has_workspace:
            QMessageBox.information(
                self,
                "No Active Workspace",
                "Create or open an audit workspace before saving.",
            )
            return False

        if self._workspace_state.workspace_file_path is None:
            return self._save_workspace_as()

        try:
            saved_path = self._workspace_service.save_state(self._workspace_state)
        except WorkspaceServiceError as error:
            QMessageBox.critical(
                self,
                "Workspace Save Failed",
                str(error),
            )
            return False

        self.statusBar().showMessage(f"Workspace saved: {saved_path.name}")

        return True

    def _save_workspace_as(self) -> bool:
        """Save the active audit workspace to a selected file."""

        identity = self._workspace_state.workspace_identity

        if identity is None:
            QMessageBox.information(
                self,
                "No Active Workspace",
                "Create or open an audit workspace before saving.",
            )
            return False

        suggested_name = self._safe_workspace_file_name(identity.name)

        initial_path = (
            self._workspace_service.default_workspace_directory / f"{suggested_name}.astworkspace"
        )

        selected_path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Audit Workspace",
            str(initial_path),
            "Auditor Support Tool Workspace (*.astworkspace)",
        )

        if not selected_path:
            return False

        try:
            saved_path = self._workspace_service.save_state(
                self._workspace_state,
                Path(selected_path),
            )
        except WorkspaceServiceError as error:
            QMessageBox.critical(
                self,
                "Workspace Save Failed",
                str(error),
            )
            return False

        self.statusBar().showMessage(
            f"Workspace saved: {saved_path.name}This is now the active workspace file."
        )

        return True

    def _confirm_workspace_transition(self) -> bool:
        """Confirm that the current workspace may be replaced or closed."""

        if not self._workspace_state.has_workspace or not self._workspace_state.is_dirty:
            return True

        identity = self._workspace_state.workspace_identity
        workspace_name = identity.name if identity is not None else "the current workspace"

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle("Unsaved Workspace Changes")
        message_box.setText(f"{workspace_name} contains unsaved changes.")
        message_box.setInformativeText("Do you want to save the changes before continuing?")

        message_box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Save)

        result = message_box.exec()

        if result == QMessageBox.StandardButton.Save:
            return self._save_workspace()

        if result == QMessageBox.StandardButton.Discard:
            return True

        return False

    @staticmethod
    def _safe_workspace_file_name(name: str) -> str:
        """Return a Windows-safe workspace file name."""

        invalid_characters = '<>:"/\\|?*'

        safe_name = "".join(
            "_" if character in invalid_characters else character for character in name.strip()
        )

        safe_name = safe_name.rstrip(". ")

        return safe_name or "Audit Workspace"

    def _create_new_workspace(self) -> None:
        """Create and activate a new audit workspace."""

        if not self._confirm_workspace_transition():
            return

        dialog = NewWorkspaceDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        identity = dialog.workspace_identity

        if identity is None:
            return

        self._workspace_state.start_workspace(identity)

        self.show_route("workspace.data_sources")

        self.statusBar().showMessage(
            f"Created workspace: {identity.name}. The workspace has not yet been saved."
        )

    def _build_menu_bar(self) -> None:
        """Create the application menu bar and keyboard shortcuts."""

        menu_bar = self.menuBar()
        menu_bar.setObjectName("applicationMenuBar")

        # ---------------------------------------------------------
        # File
        # ---------------------------------------------------------
        file_menu = menu_bar.addMenu("&File")
        file_menu.setObjectName("applicationMenu")

        new_workspace_action = QAction(
            "New Workspace",
            self,
        )
        new_workspace_action.setShortcut(QKeySequence("Ctrl+N"))
        new_workspace_action.setStatusTip("Create a new audit workspace.")
        new_workspace_action.triggered.connect(self._create_new_workspace)

        self._menu_actions["new_workspace"] = new_workspace_action
        file_menu.addAction(new_workspace_action)

        open_workspace_action = QAction(
            "Open Workspace...",
            self,
        )
        open_workspace_action.setShortcut(QKeySequence("Ctrl+O"))
        open_workspace_action.setStatusTip("Open a previously saved audit workspace.")
        open_workspace_action.triggered.connect(self._open_workspace)

        self._menu_actions["open_workspace"] = open_workspace_action
        file_menu.addAction(open_workspace_action)

        file_menu.addSeparator()

        save_workspace_action = QAction(
            "Save Workspace",
            self,
        )
        save_workspace_action.setShortcut(QKeySequence("Ctrl+S"))
        save_workspace_action.setStatusTip("Save the active audit workspace.")
        save_workspace_action.triggered.connect(self._save_workspace)

        self._menu_actions["save_workspace"] = save_workspace_action
        file_menu.addAction(save_workspace_action)

        save_workspace_as_action = QAction(
            "Save Workspace As...",
            self,
        )
        save_workspace_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_workspace_as_action.setStatusTip(
            "Save the active audit workspace to another location."
        )
        save_workspace_as_action.triggered.connect(self._save_workspace_as)

        self._menu_actions["save_workspace_as"] = save_workspace_as_action
        file_menu.addAction(save_workspace_as_action)

        file_menu.addSeparator()

        close_workspace_action = QAction(
            "Close Workspace",
            self,
        )
        close_workspace_action.setShortcut(QKeySequence("Ctrl+W"))
        close_workspace_action.setStatusTip("Close the active audit workspace.")
        close_workspace_action.triggered.connect(self._close_workspace)

        self._menu_actions["close_workspace"] = close_workspace_action
        file_menu.addAction(close_workspace_action)

        file_menu.addSeparator()

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
                key="file_data_sources",
                text="Data Sources",
                route="workspace.data_sources",
                status_tip="Register or review source files and datasets.",
            )
        )

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.setStatusTip("Close the Auditor Support Tool.")
        exit_action.triggered.connect(self.close)

        self._menu_actions["exit"] = exit_action
        file_menu.addAction(exit_action)

        # ---------------------------------------------------------
        # Workflow
        # ---------------------------------------------------------
        workflow_menu = menu_bar.addMenu("&Workflow")
        workflow_menu.setObjectName("applicationMenu")

        workflow_menu.addAction(
            self._create_route_action(
                key="workflow_data_sources",
                text="Data Sources",
                route="workspace.data_sources",
                shortcut="Ctrl+1",
                status_tip="Register source files and select audit datasets.",
            )
        )

        workflow_menu.addAction(
            self._create_route_action(
                key="workflow_data_profile",
                text="Data Profile",
                route="workspace.data_profile",
                shortcut="Ctrl+2",
                status_tip="Review dataset structure, statistics and data quality.",
            )
        )

        workflow_menu.addAction(
            self._create_route_action(
                key="workflow_data_preparation",
                text="Data Preparation",
                route="workspace.data_preparation",
                shortcut="Ctrl+3",
                status_tip="Prepare columns, names and data types for analysis.",
            )
        )

        workflow_menu.addAction(
            self._create_route_action(
                key="workflow_field_mapping",
                text="Field Mapping",
                route="workspace.field_mapping",
                shortcut="Ctrl+4",
                status_tip="Map prepared columns to standard audit fields.",
            )
        )

        # ---------------------------------------------------------
        # Settings
        # ---------------------------------------------------------
        settings_menu = menu_bar.addMenu("&Settings")
        settings_menu.setObjectName("applicationMenu")

        settings_menu.addAction(
            self._create_route_action(
                key="user_profile",
                text="User Profile",
                route="settings.user_profile",
                status_tip="Review or update the local user profile.",
            )
        )

        settings_menu.addAction(
            self._create_route_action(
                key="appearance",
                text="Appearance",
                route="settings.appearance",
                shortcut="Ctrl+,",
                status_tip="Change the application theme and appearance mode.",
            )
        )

        settings_menu.addSeparator()

        settings_menu.addAction(
            self._create_route_action(
                key="data_storage",
                text="Data && Storage",
                route="settings.data_storage",
                status_tip="Review application data and storage locations.",
            )
        )

        settings_menu.addAction(
            self._create_route_action(
                key="diagnostics",
                text="Diagnostics",
                route="settings.diagnostics",
                status_tip="Review application diagnostics.",
            )
        )

        settings_menu.addSeparator()

        settings_menu.addAction(
            self._create_route_action(
                key="updates",
                text="Check for Updates",
                route="settings.updates",
                status_tip="Check GitHub Releases for application updates.",
            )
        )

        # ---------------------------------------------------------
        # Help
        # ---------------------------------------------------------
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
                key="test_descriptions",
                text="Test Descriptions",
                route="about.test_descriptions",
                status_tip="Review available audit test descriptions.",
            )
        )

        help_menu.addSeparator()

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
        """Create a menu action that opens an application route."""

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
        """Create and register all application pages."""

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
        data_sources_page.continue_requested.connect(self.show_route)

        self._register_page(
            route="workspace.data_sources",
            title="Data Sources",
            page=data_sources_page,
        )

        data_profile_page = DataProfilePage(
            workspace_state=self._workspace_state,
        )
        data_profile_page.continue_requested.connect(self.show_route)
        data_profile_page.back_requested.connect(self.show_route)

        self._register_page(
            route="workspace.data_profile",
            title="Data Profile",
            page=data_profile_page,
        )

        data_preparation_page = DataPreparationPage(
            workspace_state=self._workspace_state,
        )
        data_preparation_page.continue_requested.connect(self.show_route)
        data_preparation_page.back_requested.connect(self.show_route)

        self._register_page(
            route="workspace.data_preparation",
            title="Data Preparation",
            page=data_preparation_page,
        )
        field_mapping_page = FieldMappingPage(
            workspace_state=self._workspace_state,
        )
        field_mapping_page.continue_requested.connect(self.show_route)
        field_mapping_page.back_requested.connect(self.show_route)

        self._register_page(
            route="workspace.field_mapping",
            title="Field Mapping",
            page=field_mapping_page,
        )

        audit_procedures_page = AuditProceduresPage(
            workspace_state=self._workspace_state,
            procedure_registry=self._procedure_registry,
        )
        audit_procedures_page.back_requested.connect(self.show_route)
        audit_procedures_page.result_ready.connect(self._handle_procedure_outcome)

        self._register_page(
            route="workspace.audit_procedures",
            title="Audit Procedures",
            page=audit_procedures_page,
        )

        self._results_page = ResultsPage(
            workspace_state=self._workspace_state,
            procedure_registry=self._procedure_registry,
        )
        self._results_page.back_requested.connect(self.show_route)

        self._workspace_state.workspace_cleared.connect(self._results_page.clear_result)
        self._workspace_state.active_dataset_changed.connect(self._results_page.clear_result)

        self._register_page(
            route="workspace.results",
            title="Results",
            page=self._results_page,
        )

        page_definitions: tuple[
            PageDefinition,
            ...,
        ] = (
            (
                "engagements.all",
                "All Engagements",
                ("Search, open and manage active audit engagements."),
            ),
            (
                "engagements.new",
                "New Engagement",
                ("Create an engagement and intentionally select its audit domain and audit area."),
            ),
            (
                "engagements.archived",
                "Archived Engagements",
                ("View and restore engagements that are no longer active."),
            ),
            (
                "workspace.overview",
                "Engagement Overview",
                (
                    "Review the current engagement, workflow "
                    "status and outstanding analysis activities."
                ),
            ),
            (
                "workspace.data_sources",
                "Data Sources",
                (
                    "Register Excel and CSV source files and "
                    "select datasets for the audit workspace."
                ),
            ),
            (
                "workspace.data_profile",
                "Data Profile",
                ("Review population statistics, detected types and data-quality information."),
            ),
            (
                "workspace.data_preparation",
                "Data Preparation",
                (
                    "Confirm prepared column names, data types "
                    "and included columns before field mapping."
                ),
            ),
            (
                "workspace.field_mapping",
                "Field Mapping",
                ("Map auditee-specific source columns to standard audit fields."),
            ),
            (
                "workspace.audit_procedures",
                "Audit Procedures",
                ("Select and configure procedures available for the engagement's audit domain."),
            ),
            (
                "workspace.results",
                "Results",
                ("Review procedure results and combined transaction risk."),
            ),
            (
                "workspace.investigation",
                "Investigation",
                ("Select records for follow-up, add notes and assign preliminary statuses."),
            ),
            (
                "reports.generate",
                "Generate Reports",
                ("Generate audit working papers and structured exception reports."),
            ),
            (
                "reports.export",
                "Export Results",
                ("Export full results or selected investigation records."),
            ),
            (
                "reports.previous",
                "Previous Reports",
                ("Open reports previously generated for an engagement."),
            ),
            (
                "settings.data_storage",
                "Data & Storage",
                ("Review application paths, engagement locations and temporary-storage usage."),
            ),
            (
                "settings.ai_browser",
                "AI Browser Access",
                ("Configure the approved browser-based local AI service."),
            ),
            (
                "settings.backup_restore",
                "Backup & Restore",
                ("Create and restore engagement or application-managed backups."),
            ),
            (
                "settings.reset",
                "Reset Application",
                ("Reset settings, clear temporary data or perform a factory reset."),
            ),
            (
                "settings.diagnostics",
                "Diagnostics",
                (
                    "Review application version, environment, "
                    "paths and non-sensitive diagnostic "
                    "information."
                ),
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
        """Register a page with the application router."""

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
        """Open a PDF using the saved viewing preference."""

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

    @staticmethod
    def _workspace_stage_for_route(
        route: str,
    ) -> WorkspaceStage | None:
        """Return the readiness stage associated with a workspace route."""

        route_stages = {
            "workspace.data_sources": WorkspaceStage.DATA_SOURCES,
            "workspace.data_profile": WorkspaceStage.DATA_PROFILE,
            "workspace.data_preparation": WorkspaceStage.DATA_PREPARATION,
            "workspace.field_mapping": WorkspaceStage.FIELD_MAPPING,
            "workspace.audit_procedures": WorkspaceStage.AUDIT_PROCEDURES,
        }

        return route_stages.get(route)

    def _workspace_route_is_ready(
        self,
        route: str,
    ) -> bool:
        """Return whether a guarded workspace route may be opened."""

        stage = self._workspace_stage_for_route(route)

        if stage is None:
            return True

        result = self._workspace_readiness_service.check(
            self._workspace_state,
            stage,
        )

        if result.ready:
            return True

        self._show_readiness_warning(result.message)

        return False

    def _show_readiness_warning(
        self,
        message: str,
    ) -> None:
        """Show a prominent temporary workflow-readiness warning."""

        self.statusBar().clearMessage()

        self._readiness_warning_label.setText(f"⚠ {message}   |   Version {APP_VERSION}")
        self._readiness_warning_label.setVisible(True)

        self._readiness_warning_timer.start(8000)

    def _clear_readiness_warning(self) -> None:
        """Hide the temporary workflow-readiness warning."""

        self._readiness_warning_timer.stop()
        self._readiness_warning_label.clear()
        self._readiness_warning_label.setVisible(False)

    def _breadcrumb_parts_for_route(
        self,
        *,
        route: str,
        title: str,
    ) -> tuple[str, ...]:
        """Return the breadcrumb hierarchy for an application route."""

        if route == "dashboard":
            return ("Dashboard",)

        if route == "workspace.results":
            results_page = getattr(
                self,
                "_results_page",
                None,
            )

            if results_page is not None and results_page.outcome is not None:
                return (
                    "Audit Workspace",
                    "Audit Procedures",
                    results_page.procedure_breadcrumb_title,
                    "Results",
                )

        if route.startswith("workspace."):
            return (
                "Audit Workspace",
                title,
            )

        if route.startswith("engagements."):
            return (
                "Engagements",
                title,
            )

        if route.startswith("reports."):
            return (
                "Reports",
                title,
            )

        if route.startswith("settings."):
            return (
                "Settings",
                title,
            )

        if route.startswith("about."):
            return (
                "Help",
                title,
            )

        return (title,)

    def show_route(
        self,
        route: str,
    ) -> None:
        """Display the page registered for a route."""

        current_page = self._page_stack.currentWidget()

        if current_page is self._pdf_viewer_page and route != "about.pdf_viewer":
            self._pdf_viewer_page.close_document()

        if self._profile_required and route != "settings.user_profile":
            route = "settings.user_profile"

            self.statusBar().showMessage("Complete the local user profile to continue.")

        if not self._workspace_route_is_ready(route):
            return

        page = self._pages.get(route)

        if page is None:
            self.statusBar().showMessage(f"Unknown page: {route}   |   Version {APP_VERSION}")
            return

        self._clear_readiness_warning()

        self._page_stack.setCurrentWidget(page)
        self._sidebar.set_active_route(route)

        title = self._page_titles[route]

        self._breadcrumb_bar.set_parts(
            self._breadcrumb_parts_for_route(
                route=route,
                title=title,
            )
        )

        status = "Profile setup required" if self._profile_required else "Ready"

        self.statusBar().showMessage(f"{title}   |   {status}   |   Version {APP_VERSION}")

    def _handle_procedure_outcome(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Open the dedicated Results page for a procedure outcome."""

        self._results_page.set_outcome(outcome)
        self.show_route("workspace.results")

    def _handle_profile_saved(
        self,
        profile: UserProfile,
    ) -> None:
        """Unlock the application after profile completion."""

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

    def _open_workspace(self) -> None:
        """Open a previously saved audit workspace."""

        if not self._confirm_workspace_transition():
            return

        selected_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Audit Workspace",
            str(self._workspace_service.default_workspace_directory),
            "Auditor Support Tool Workspace (*.astworkspace)",
        )

        if not selected_path:
            return

        workspace_path = Path(selected_path)
        integrity_mismatch_accepted = False

        try:
            document = self._workspace_service.load_into_state(
                self._workspace_state,
                workspace_path,
            )
        except WorkspaceSourceIntegrityError as error:
            warning = QMessageBox(self)
            warning.setIcon(QMessageBox.Icon.Warning)
            warning.setWindowTitle("Source Integrity Warning")
            warning.setText(
                "The saved workspace source file no longer matches "
                "the SHA-256 hash recorded when the workspace was saved."
            )
            warning.setInformativeText(
                "This may mean the source data was changed outside the "
                "Auditor Support Tool. Open the workspace only if you "
                "understand and accept this integrity exception."
            )
            warning.setDetailedText(
                f"Source: {error.source_path}\n"
                f"Expected SHA-256: {error.expected_sha256}\n"
                f"Actual SHA-256:   {error.actual_sha256}"
            )
            warning.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            warning.setDefaultButton(QMessageBox.StandardButton.Cancel)

            if warning.exec() != QMessageBox.StandardButton.Yes:
                return

            try:
                document = self._workspace_service.load_into_state(
                    self._workspace_state,
                    workspace_path,
                    allow_source_integrity_mismatch=True,
                )
            except WorkspaceServiceError as retry_error:
                QMessageBox.critical(
                    self,
                    "Workspace Open Failed",
                    str(retry_error),
                )
                return

            integrity_mismatch_accepted = True

        except WorkspaceServiceError as error:
            QMessageBox.critical(
                self,
                "Workspace Open Failed",
                str(error),
            )
            return

        self.show_route("workspace.data_sources")

        if integrity_mismatch_accepted:
            self._show_readiness_warning("Workspace opened with a source integrity warning.")
        else:
            self.statusBar().showMessage(f"Workspace opened: {document.identity.name}")

    def _close_workspace(self) -> None:
        """Close the active audit workspace."""

        if not self._workspace_state.has_workspace:
            QMessageBox.information(
                self,
                "No Active Workspace",
                "There is no audit workspace currently open.",
            )
            return

        if not self._confirm_workspace_transition():
            return

        self._workspace_state.clear()
        self.show_route("dashboard")

        self.statusBar().showMessage("Audit workspace closed.")

    def closeEvent(
        self,
        event: QCloseEvent,
    ) -> None:
        """Protect unsaved workspace changes when closing the application."""

        if self._confirm_workspace_transition():
            event.accept()
            return

        event.ignore()
