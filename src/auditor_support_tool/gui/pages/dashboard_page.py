"""Dashboard page."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class DashboardPage(QWidget):
    """General application dashboard."""

    route_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("dashboardPage")
        self._build_interface()

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Manage engagements, review audit progress and access "
            "the tools required for the current audit."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(10)

        new_engagement_button = self._create_action_button(
            "New Engagement",
            "engagements.new",
            primary=True,
        )
        open_engagement_button = self._create_action_button(
            "Open Engagement",
            "engagements.all",
        )
        previous_reports_button = self._create_action_button(
            "Previous Reports",
            "reports.previous",
        )

        quick_actions.addWidget(new_engagement_button)
        quick_actions.addWidget(open_engagement_button)
        quick_actions.addWidget(previous_reports_button)
        quick_actions.addStretch()

        cards = QGridLayout()
        cards.setHorizontalSpacing(16)
        cards.setVerticalSpacing(16)
        cards.setColumnStretch(0, 1)
        cards.setColumnStretch(1, 1)

        current_engagement = self._create_card(
            title="Current Engagement",
            status="No engagement selected",
            description=(
                "Create a new engagement or open an existing one to begin audit analysis."
            ),
            action_label="Create Engagement",
            route="engagements.new",
        )

        workflow_status = self._create_card(
            title="Audit Workflow",
            status="Not started",
            description=(
                "Data sources, field mappings, audit procedures and "
                "investigation results will appear here."
            ),
            action_label="Open Audit Workspace",
            route="workspace.overview",
        )

        ai_access = self._create_card(
            title="Local AI Access",
            status="Not configured",
            description=(
                "The approved AI service will open in the default browser. "
                "Report upload remains a manual process."
            ),
            action_label="Configure AI Access",
            route="settings.ai_browser",
        )

        recent_reports = self._create_card(
            title="Recent Reports",
            status="No reports generated",
            description=(
                "Generated working papers and exception reports "
                "will be listed within each engagement."
            ),
            action_label="View Reports",
            route="reports.previous",
        )

        cards.addWidget(current_engagement, 0, 0)
        cards.addWidget(workflow_status, 0, 1)
        cards.addWidget(ai_access, 1, 0)
        cards.addWidget(recent_reports, 1, 1)

        activity_card = self._create_activity_card()

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(quick_actions)
        layout.addSpacing(4)
        layout.addLayout(cards)
        layout.addWidget(activity_card)
        layout.addStretch()

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _create_action_button(
        self,
        label: str,
        route: str,
        primary: bool = False,
    ) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("primaryActionButton" if primary else "secondaryActionButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False: self.route_requested.emit(route))
        return button

    def _create_card(
        self,
        title: str,
        status: str,
        description: str,
        action_label: str,
        route: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(8)

        card_title = QLabel(title)
        card_title.setObjectName("cardTitle")

        card_status = QLabel(status)
        card_status.setObjectName("cardStatus")

        card_description = QLabel(description)
        card_description.setObjectName("cardText")
        card_description.setWordWrap(True)

        card_action = QPushButton(action_label)
        card_action.setObjectName("cardActionButton")
        card_action.setCursor(Qt.CursorShape.PointingHandCursor)
        card_action.clicked.connect(lambda checked=False: self.route_requested.emit(route))

        layout.addWidget(card_title)
        layout.addWidget(card_status)
        layout.addWidget(card_description)
        layout.addStretch()
        layout.addWidget(card_action, 0, Qt.AlignmentFlag.AlignLeft)

        return card

    def _create_activity_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(8)

        title = QLabel("Recent Activity")
        title.setObjectName("cardTitle")

        empty_state = QLabel(
            "There is no recent activity. Engagement creation, imports, "
            "procedure runs and reports will be recorded here."
        )
        empty_state.setObjectName("cardText")
        empty_state.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(empty_state)

        return card
