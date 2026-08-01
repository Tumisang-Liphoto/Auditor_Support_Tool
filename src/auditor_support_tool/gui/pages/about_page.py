"""Application information page."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
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

from auditor_support_tool.core.constants import (
    APP_NAME,
    APP_VERSION,
    GITHUB_REPOSITORY_NAME,
    GITHUB_REPOSITORY_OWNER,
)


class AboutPage(QWidget):
    """Display application identity, purpose and support information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(22)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("About")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Application information, purpose and support resources for the Auditor Support Tool."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_application_card())
        layout.addWidget(self._build_purpose_card())
        layout.addWidget(self._build_support_card())

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_application_card(self) -> QFrame:
        card = self._create_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(16)

        title = QLabel("Application information")
        title.setObjectName("profileSectionTitle")

        details = QGridLayout()
        details.setHorizontalSpacing(28)
        details.setVerticalSpacing(10)
        details.setColumnMinimumWidth(0, 170)
        details.setColumnStretch(1, 1)

        details.addWidget(self._field_label("Application"), 0, 0)
        details.addWidget(self._value_label(APP_NAME), 0, 1)

        details.addWidget(self._field_label("Installed version"), 1, 0)
        details.addWidget(self._value_label(APP_VERSION), 1, 1)

        layout.addWidget(title)
        layout.addLayout(details)

        return card

    def _build_purpose_card(self) -> QFrame:
        card = self._create_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(12)

        title = QLabel("Purpose")
        title.setObjectName("profileSectionTitle")

        text = QLabel(
            "The Auditor Support Tool provides a structured desktop "
            "workspace for audit engagements, data preparation, audit "
            "procedures, review of results, investigation and reporting. "
            "Its core functions are designed to operate locally and "
            "support controlled audit work."
        )
        text.setObjectName("profileSectionDescription")
        text.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(text)

        return card

    def _build_support_card(self) -> QFrame:
        card = self._create_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(14)

        title = QLabel("Support and project information")
        title.setObjectName("profileSectionTitle")

        description = QLabel(
            "Use the project repository to review releases and report "
            "technical issues. Do not include confidential audit "
            "information in public issue reports."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        actions = QHBoxLayout()
        actions.setSpacing(12)

        repository_button = QPushButton("Open GitHub Repository")
        repository_button.setObjectName("primaryActionButton")
        repository_button.setCursor(Qt.CursorShape.PointingHandCursor)
        repository_button.clicked.connect(self._open_repository)

        releases_button = QPushButton("View Releases")
        releases_button.setObjectName("secondaryActionButton")
        releases_button.setCursor(Qt.CursorShape.PointingHandCursor)
        releases_button.clicked.connect(self._open_releases)

        actions.addWidget(repository_button)
        actions.addWidget(releases_button)
        actions.addStretch()

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(actions)

        return card

    def _open_repository(self) -> None:
        QDesktopServices.openUrl(QUrl(self._repository_url()))

    def _open_releases(self) -> None:
        QDesktopServices.openUrl(QUrl(f"{self._repository_url()}/releases"))

    @staticmethod
    def _repository_url() -> str:
        return f"https://github.com/{GITHUB_REPOSITORY_OWNER}/{GITHUB_REPOSITORY_NAME}"

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _value_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("updateValue")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _create_card() -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        return card
