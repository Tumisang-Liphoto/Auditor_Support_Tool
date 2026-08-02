"""Bundled audit test-description catalogue."""

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
class TestDescriptionDefinition:
    """Description of a bundled audit-test document."""

    test_code: str
    title: str
    category: str
    description: str
    file_name: str


TEST_DESCRIPTIONS: tuple[TestDescriptionDefinition, ...] = (
    TestDescriptionDefinition(
        test_code="GL-001",
        title="Duplicate Invoice Detection",
        category="General Ledger",
        description=(
            "Identifies repeated invoice numbers that may require "
            "further audit scrutiny."
        ),
        file_name="GL-001-Duplicate-Invoice-Detection.pdf",
    ),
)


class TestDescriptionPage(QWidget):
    """List and open bundled audit-test descriptions."""

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
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        content.setObjectName("pageContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Test Descriptions")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Review the purpose, data requirements, risks and limitations "
            "of available audit tests."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        for definition in TEST_DESCRIPTIONS:
            layout.addWidget(
                self._build_description_card(definition)
            )

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_description_card(
        self,
        definition: TestDescriptionDefinition,
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

        title = QLabel(
            f"{definition.test_code} — {definition.title}"
        )
        title.setObjectName("profileSectionTitle")

        category = QLabel(definition.category)
        category.setObjectName("fieldHint")

        description = QLabel(definition.description)
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        path = (
            self._test_descriptions_directory()
            / definition.file_name
        )

        status = QLabel(
            "Available"
            if path.is_file()
            else "Test description not yet available"
        )
        status.setObjectName("formStatus")
        status.setProperty(
            "status",
            "success" if path.is_file() else "neutral",
        )

        button = QPushButton("Open Description")
        button.setObjectName("primaryActionButton")
        button.setEnabled(path.is_file())

        button.clicked.connect(
            lambda checked=False,
            selected_definition=definition,
            document_path=path: self._request_document(
                selected_definition,
                document_path,
            )
        )

        text_layout.addWidget(title)
        text_layout.addWidget(category)
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
        definition: TestDescriptionDefinition,
        path: Path,
    ) -> None:
        """Request that the main window open the PDF viewer."""

        if not path.is_file():
            return

        self.document_requested.emit(
            str(path.resolve()),
            definition.title,
            f"{definition.test_code} | {definition.category}",
            "about.test_descriptions",
        )

    @staticmethod
    def _test_descriptions_directory() -> Path:
        """Return the bundled General Ledger description directory."""

        if (
            getattr(sys, "frozen", False)
            and hasattr(sys, "_MEIPASS")
        ):
            return (
                Path(sys._MEIPASS)
                / "auditor_support_tool"
                / "resources"
                / "test_descriptions"
                / "general_ledger"
            )

        return (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "test_descriptions"
            / "general_ledger"
        )