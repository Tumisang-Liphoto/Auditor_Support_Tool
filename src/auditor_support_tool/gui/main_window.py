"""Primary application window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
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


class MainWindow(QMainWindow):
    """Main window for the Auditor Support Tool."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)
        self.setMinimumSize(MINIMUM_WINDOW_WIDTH, MINIMUM_WINDOW_HEIGHT)

        self._build_interface()
        self.statusBar().showMessage(f"Ready   |   Version {APP_VERSION}")

    def _build_interface(self) -> None:
        central_widget = QWidget(self)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        content = self._build_content()

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content, 1)

        self.setCentralWidget(central_widget)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(8)

        application_name = QLabel(APP_NAME)
        application_name.setObjectName("applicationName")
        application_name.setWordWrap(True)

        layout.addWidget(application_name)
        layout.addSpacing(24)

        for label in (
            "Dashboard",
            "Engagements",
            "Audit Workspace",
            "Reports",
            "Settings",
        ):
            button = QPushButton(label)
            button.setObjectName("navigationButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            layout.addWidget(button)

        layout.addStretch()

        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setObjectName("sidebarVersion")
        layout.addWidget(version_label)

        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("contentArea")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Welcome to the Auditor Support Tool. "
            "The application foundation is running successfully."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        status_card = QFrame()
        status_card.setObjectName("card")

        card_layout = QVBoxLayout(status_card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(8)

        card_title = QLabel("Application Foundation")
        card_title.setObjectName("cardTitle")

        card_text = QLabel(
            "The desktop interface, application paths and development "
            "environment have been configured."
        )
        card_text.setObjectName("cardText")
        card_text.setWordWrap(True)

        card_layout.addWidget(card_title)
        card_layout.addWidget(card_text)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(status_card)
        layout.addStretch()

        return content