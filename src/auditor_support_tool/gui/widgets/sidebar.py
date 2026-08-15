"""Expandable application sidebar navigation."""

from collections.abc import Sequence

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.constants import APP_NAME
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)
from auditor_support_tool.gui.widgets.workspace_context_panel import (
    WorkspaceContextPanel,
)

NavigationItem = tuple[str, str]
NavigationGroupDefinition = tuple[
    str,
    str,
    tuple[NavigationItem, ...],
]

_ACTION_ROUTES = {
    "workspace.new",
}

_SIDEBAR_ICON_COLOR = "#F4F7F5"
_NAVIGATION_ICON_SIZE = QSize(16, 16)


class NavigationGroup(QWidget):
    """Expandable collection of related navigation buttons."""

    route_selected = Signal(str)
    expansion_changed = Signal(bool)

    def __init__(
        self,
        *,
        title: str,
        icon_name: str,
        items: Sequence[NavigationItem],
        button_group: QButtonGroup,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title = title

        self._route_buttons: dict[
            str,
            QPushButton,
        ] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(3)

        self._header = QToolButton()
        self._header.setObjectName("navigationGroupHeader")

        self._header.setIcon(
            qta.icon(
                icon_name,
                color=_SIDEBAR_ICON_COLOR,
            )
        )
        self._header.setIconSize(_NAVIGATION_ICON_SIZE)

        self._header.setText(self._header_text(expanded=False))

        self._header.setCheckable(True)
        self._header.setChecked(False)

        self._header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self._header.setCursor(Qt.CursorShape.PointingHandCursor)

        self._header.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._header.clicked.connect(self._handle_header_clicked)

        self._content = QWidget()
        self._content.setObjectName("navigationGroupContent")

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(
            8,
            0,
            0,
            4,
        )
        content_layout.setSpacing(2)

        for label, route in items:
            button = QPushButton(label)
            button.setObjectName("navigationChildButton")

            is_action = route in _ACTION_ROUTES

            button.setCheckable(not is_action)

            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            button.clicked.connect(
                lambda checked=False, selected_route=route: self.route_selected.emit(selected_route)
            )

            if not is_action:
                button_group.addButton(button)

            self._route_buttons[route] = button

            content_layout.addWidget(button)

        self._content.setVisible(False)

        layout.addWidget(self._header)

        layout.addWidget(self._content)

    @property
    def route_buttons(
        self,
    ) -> dict[str, QPushButton]:
        """Return the buttons registered under this group."""

        return self._route_buttons

    def _handle_header_clicked(
        self,
        expanded: bool,
    ) -> None:
        """Apply a user-requested expansion change."""

        self.set_expanded(expanded)

        self.expansion_changed.emit(expanded)

    def set_expanded(
        self,
        expanded: bool,
    ) -> None:
        """Expand or collapse the group's child navigation items."""

        self._header.setChecked(expanded)

        self._content.setVisible(expanded)

        self._header.setText(self._header_text(expanded=expanded))

    def _header_text(
        self,
        *,
        expanded: bool,
    ) -> str:
        """Return group text with a compact expansion indicator."""

        indicator = "▾" if expanded else "▸"

        return f"{indicator}  {self._title}"


class Sidebar(QFrame):
    """Persistent application sidebar."""

    route_selected = Signal(str)

    def __init__(
        self,
        *,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("sidebar")

        self.setFixedWidth(280)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._route_buttons: dict[
            str,
            QPushButton,
        ] = {}

        self._route_groups: dict[
            str,
            NavigationGroup,
        ] = {}

        self._navigation_groups: list[NavigationGroup] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            14,
            20,
            14,
            16,
        )
        layout.setSpacing(7)

        application_name = QLabel(APP_NAME)
        application_name.setObjectName("applicationName")
        application_name.setWordWrap(True)

        application_subtitle = QLabel("Audit analytics and support")
        application_subtitle.setObjectName("applicationSubtitle")
        application_subtitle.setWordWrap(True)

        layout.addWidget(application_name)

        layout.addWidget(application_subtitle)

        layout.addSpacing(18)

        dashboard_button = self._create_route_button(
            label="Dashboard",
            route="dashboard",
            icon_name="fa5s.home",
        )

        layout.addWidget(dashboard_button)

        groups: tuple[
            NavigationGroupDefinition,
            ...,
        ] = (
            (
                "Engagements",
                "fa5s.briefcase",
                (
                    (
                        "All Engagements",
                        "engagements.all",
                    ),
                    (
                        "New Engagement",
                        "engagements.new",
                    ),
                    (
                        "Archived Engagements",
                        "engagements.archived",
                    ),
                ),
            ),
            (
                "Audit Workspace",
                "fa5s.tasks",
                (
                    (
                        "New Workspace",
                        "workspace.new",
                    ),
                    (
                        "Engagement Overview",
                        "workspace.overview",
                    ),
                    (
                        "Data Sources",
                        "workspace.data_sources",
                    ),
                    (
                        "Data Profile",
                        "workspace.data_profile",
                    ),
                    (
                        "Data Preparation",
                        "workspace.data_preparation",
                    ),
                    (
                        "Field Mapping",
                        "workspace.field_mapping",
                    ),
                    (
                        "Audit Procedures",
                        "workspace.audit_procedures",
                    ),
                    (
                        "Results",
                        "workspace.results",
                    ),
                    (
                        "Investigation",
                        "workspace.investigation",
                    ),
                ),
            ),
            (
                "Reports",
                "fa5s.file-alt",
                (
                    (
                        "Generate Reports",
                        "reports.generate",
                    ),
                    (
                        "Export Results",
                        "reports.export",
                    ),
                    (
                        "Previous Reports",
                        "reports.previous",
                    ),
                ),
            ),
            (
                "Settings",
                "fa5s.cog",
                (
                    (
                        "User Profile",
                        "settings.user_profile",
                    ),
                    (
                        "Appearance",
                        "settings.appearance",
                    ),
                    (
                        "Data && Storage",
                        "settings.data_storage",
                    ),
                    (
                        "AI Browser Access",
                        "settings.ai_browser",
                    ),
                    (
                        "Backup && Restore",
                        "settings.backup_restore",
                    ),
                    (
                        "Reset Application",
                        "settings.reset",
                    ),
                    (
                        "Diagnostics",
                        "settings.diagnostics",
                    ),
                ),
            ),
            (
                "About",
                "fa5s.info-circle",
                (
                    (
                        "Overview",
                        "about.overview",
                    ),
                    (
                        "Updates",
                        "settings.updates",
                    ),
                    (
                        "Manuals",
                        "about.manuals",
                    ),
                    (
                        "Test Descriptions",
                        "about.test_descriptions",
                    ),
                ),
            ),
        )

        for (
            group_title,
            icon_name,
            group_items,
        ) in groups:
            group = NavigationGroup(
                title=group_title,
                icon_name=icon_name,
                items=group_items,
                button_group=(self._button_group),
            )

            group.route_selected.connect(self.route_selected.emit)

            group.expansion_changed.connect(
                lambda expanded, selected_group=group: self._handle_group_expansion(
                    selected_group,
                    expanded,
                )
            )

            self._navigation_groups.append(group)

            for _, route in group_items:
                self._route_buttons[route] = group.route_buttons[route]

                self._route_groups[route] = group

            layout.addWidget(group)

        layout.addStretch()

        self._workspace_context = WorkspaceContextPanel(
            workspace_state=(workspace_state),
        )

        layout.addWidget(self._workspace_context)

    def _create_route_button(
        self,
        *,
        label: str,
        route: str,
        icon_name: str,
    ) -> QPushButton:
        """Create a top-level route button."""

        button = QPushButton(label)

        button.setObjectName("navigationButton")

        button.setIcon(
            qta.icon(
                icon_name,
                color=_SIDEBAR_ICON_COLOR,
            )
        )

        button.setIconSize(_NAVIGATION_ICON_SIZE)

        button.setCheckable(True)

        button.setCursor(Qt.CursorShape.PointingHandCursor)

        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        button.clicked.connect(lambda checked=False: self.route_selected.emit(route))

        self._button_group.addButton(button)

        self._route_buttons[route] = button

        return button

    def _handle_group_expansion(
        self,
        selected_group: NavigationGroup,
        expanded: bool,
    ) -> None:
        """Collapse other groups when one group is expanded."""

        if not expanded:
            return

        for group in self._navigation_groups:
            if group is not selected_group:
                group.set_expanded(False)

    def set_active_route(
        self,
        route: str,
    ) -> None:
        """Highlight a route and reveal its parent group."""

        button = self._route_buttons.get(route)

        if button is None:
            return

        parent_group = self._route_groups.get(route)

        if parent_group is not None:
            self._handle_group_expansion(
                parent_group,
                True,
            )

            parent_group.set_expanded(True)

        if button.isCheckable():
            button.setChecked(True)
