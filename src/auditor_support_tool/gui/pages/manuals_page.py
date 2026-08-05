"""Bundled application manuals page."""

import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class ManualDefinition:
    """Description of a bundled application manual."""

    title: str
    description: str
    file_name: str


MANUALS: tuple[ManualDefinition, ...] = (
    ManualDefinition(
        "PDF Viewer Test Manual",
        (
            "Temporary two-page manual used to test scrolling, zooming, "
            "fit-to-width and navigation inside the application."
        ),
        "pdf-viewer-test-manual.pdf",
    ),
    ManualDefinition(
        "User Manual",
        "Guidance for everyday use of the Auditor Support Tool.",
        "user-manual.pdf",
    ),
    ManualDefinition(
        "Installation Guide",
        "Instructions for installing the application for a Windows user.",
        "installation-guide.pdf",
    ),
    ManualDefinition(
        "Update Guide",
        "Guidance on update channels, downloads and recovery.",
        "update-guide.pdf",
    ),
    ManualDefinition(
        "Administrator Guide",
        "Configuration, support and deployment guidance.",
        "administrator-guide.pdf",
    ),
)


class ManualsPage(QWidget):
    """List and open manuals bundled with the application."""

    document_requested = Signal(
        str,
        str,
        str,
        str,
    )

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
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Manuals")
        title.setObjectName("pageTitle")

        subtitle = QLabel("Open guidance documents supplied with the Auditor Support Tool.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        for manual in MANUALS:
            layout.addWidget(self._build_manual_card(manual))

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_manual_card(
        self,
        manual: ManualDefinition,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QHBoxLayout(card)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(20)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)

        title = QLabel(manual.title)
        title.setObjectName("profileSectionTitle")

        description = QLabel(manual.description)
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        path = self._manuals_directory() / manual.file_name

        status = QLabel("Available" if path.is_file() else "Manual not yet available")
        status.setObjectName("formStatus")
        status.setProperty(
            "status",
            "success" if path.is_file() else "neutral",
        )

        button = QPushButton("Open Manual")
        button.setObjectName("primaryActionButton")
        button.setEnabled(path.is_file())

        button.clicked.connect(
            lambda checked=False, selected_manual=manual, manual_path=path: self._request_document(
                selected_manual,
                manual_path,
            )
        )

        text_layout.addWidget(title)
        text_layout.addWidget(description)
        text_layout.addWidget(status)

        layout.addLayout(text_layout, 1)
        layout.addWidget(
            button,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )

        return card

    def _request_document(
        self,
        manual: ManualDefinition,
        path: Path,
    ) -> None:
        """Request that the main window open a manual."""

        if not path.is_file():
            return

        self.document_requested.emit(
            str(path.resolve()),
            manual.title,
            "Application Manual",
            "about.manuals",
        )

    @staticmethod
    def _manuals_directory() -> Path:
        """Return the bundled manuals directory."""

        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS) / "auditor_support_tool" / "resources" / "manuals"

        return Path(__file__).resolve().parents[2] / "resources" / "manuals"
