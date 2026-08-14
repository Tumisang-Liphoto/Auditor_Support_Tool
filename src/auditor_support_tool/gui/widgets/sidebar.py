"""Expandable application sidebar navigation."""

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
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

from auditor_support_tool.core.constants import APP_NAME, APP_VERSION

NavigationItem = tuple[str, str]

_ACTION_ROUTES = {
    "workspace.new",
}


class NavigationGroup(QWidget):
    """Expandable collection of related navigation buttons."""

    route_selected = Signal(str)
    expansion_changed = Signal(bool)

    def __init__(
        self,
        title: str,
        items: Sequence[NavigationItem],
        button_group: QButtonGroup,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._route_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._header = QToolButton()
        self._header.setObjectName("navigationGroupHeader")
        self._header.setText(title)
        self._header.setCheckable(True)
        self._header.setChecked(False)
        self._header.setArrowType(Qt.ArrowType.RightArrow)
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
        content_layout.setContentsMargins(12, 0, 0, 4)
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
    def route_buttons(self) -> dict[str, QPushButton]:
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
        self._header.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)


class Sidebar(QFrame):
    """Persistent application sidebar."""

    route_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("sidebar")
        self.setFixedWidth(255)

        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._route_buttons: dict[str, QPushButton] = {}
        self._route_groups: dict[str, NavigationGroup] = {}
        self._navigation_groups: list[NavigationGroup] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
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
        )
        layout.addWidget(dashboard_button)

        groups: tuple[
            tuple[str, tuple[NavigationItem, ...]],
            ...,
        ] = (
            (
                "Engagements",
                (
                    ("All Engagements", "engagements.all"),
                    ("New Engagement", "engagements.new"),
                    ("Archived Engagements", "engagements.archived"),
                ),
            ),
            (
                "Audit Workspace",
                (
                    ("New Workspace", "workspace.new"),
                    ("Engagement Overview", "workspace.overview"),
                    ("Data Sources", "workspace.data_sources"),
                    ("Data Profile", "workspace.data_profile"),
                    (
                        "Data Preparation",
                        "workspace.data_preparation",
                    ),
                    ("Field Mapping", "workspace.field_mapping"),
                    ("Audit Procedures", "workspace.audit_procedures"),
                    ("Results", "workspace.results"),
                    ("Investigation", "workspace.investigation"),
                ),
            ),
            (
                "Reports",
                (
                    ("Generate Reports", "reports.generate"),
                    ("Export Results", "reports.export"),
                    ("Previous Reports", "reports.previous"),
                ),
            ),
            (
                "Settings",
                (
                    ("User Profile", "settings.user_profile"),
                    ("Appearance", "settings.appearance"),
                    ("Data && Storage", "settings.data_storage"),
                    ("AI Browser Access", "settings.ai_browser"),
                    ("Backup && Restore", "settings.backup_restore"),
                    ("Reset Application", "settings.reset"),
                    ("Diagnostics", "settings.diagnostics"),
                ),
            ),
            (
                "About",
                (
                    ("Overview", "about.overview"),
                    ("Updates", "settings.updates"),
                    ("Manuals", "about.manuals"),
                    ("Test Descriptions", "about.test_descriptions"),
                ),
            ),
        )

        for group_title, group_items in groups:
            group = NavigationGroup(
                title=group_title,
                items=group_items,
                button_group=self._button_group,
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

        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setObjectName("sidebarVersion")

        layout.addWidget(version_label)

    def _create_route_button(
        self,
        label: str,
        route: str,
    ) -> QPushButton:
        """Create a top-level route button."""

        button = QPushButton(label)
        button.setObjectName("navigationButton")
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

    def set_active_route(self, route: str) -> None:
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
