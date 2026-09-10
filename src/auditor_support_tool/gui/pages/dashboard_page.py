"""Dashboard page."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
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
            "Start a new audit or open a saved audit, then follow the steps under Current Audit."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        quick_actions = QHBoxLayout()
        quick_actions.setSpacing(10)

        new_audit_button = self._create_action_button(
            "New Audit",
            "workspace.new",
            primary=True,
        )
        open_audit_button = self._create_action_button(
            "Open Audit",
            "workspace.open",
        )

        quick_actions.addWidget(new_audit_button)
        quick_actions.addWidget(open_audit_button)
        quick_actions.addStretch()

        workflow_card = QFrame()
        workflow_card.setObjectName("card")

        workflow_layout = QVBoxLayout(workflow_card)
        workflow_layout.setContentsMargins(22, 20, 22, 20)
        workflow_layout.setSpacing(8)

        workflow_title = QLabel("Audit Workflow")
        workflow_title.setObjectName("cardTitle")

        workflow_text = QLabel(
            "Add audit data → Review the data profile → Prepare data → Map fields → "
            "Run audit procedures → Review results."
        )
        workflow_text.setObjectName("cardText")
        workflow_text.setWordWrap(True)

        workflow_hint = QLabel(
            "When an audit is open, its name and status are shown at the bottom "
            "of the navigation panel."
        )
        workflow_hint.setObjectName("cardText")
        workflow_hint.setWordWrap(True)

        workflow_layout.addWidget(workflow_title)
        workflow_layout.addWidget(workflow_text)
        workflow_layout.addWidget(workflow_hint)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(quick_actions)
        layout.addSpacing(4)
        layout.addWidget(workflow_card)
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
