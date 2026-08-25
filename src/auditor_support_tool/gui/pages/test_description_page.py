"""Bundled audit test-description catalogue and contextual detail page."""

from __future__ import annotations

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

from auditor_support_tool.core.test_description_catalogue import (
    TEST_DESCRIPTIONS,
    TestDescriptionDefinition,
    description_document_path,
    get_test_description_definition,
)


class TestDescriptionPage(QWidget):
    """List descriptions or show one description in a caller-aware context."""

    document_requested = Signal(
        str,
        str,
        str,
        str,
    )
    back_requested = Signal(str)

    def __init__(
        self,
        *,
        page_route: str = "about.test_descriptions",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._page_route = page_route
        self._return_route: str | None = None
        self._current_definition: TestDescriptionDefinition | None = None

        self._build_interface()
        self.show_catalogue()

    @property
    def breadcrumb_title(self) -> str:
        """Return the focused procedure title for breadcrumbs."""

        definition = self._current_definition

        if definition is None:
            return "Test Description"

        return f"{definition.test_code} {definition.title}"

    def show_catalogue(self) -> None:
        """Show the normal Help catalogue without a contextual Back button."""

        self._return_route = None
        self._current_definition = None

        self._back_button.setVisible(False)
        self._title.setText("Test Descriptions")
        self._subtitle.setText(
            "Review the purpose, data requirements, risks and limitations of available audit tests."
        )

        self._rebuild_cards(TEST_DESCRIPTIONS)

    def show_test(
        self,
        test_code: str,
        *,
        return_route: str,
    ) -> bool:
        """Show one description and remember which page opened it."""

        definition = get_test_description_definition(test_code)

        if definition is None:
            return False

        self._return_route = return_route
        self._current_definition = definition

        self._back_button.setText(self._back_button_text(return_route))
        self._back_button.setVisible(True)

        self._title.setText("Test Description")
        self._subtitle.setText(f"{definition.test_code} — {definition.title}")

        self._rebuild_cards((definition,))

        return True

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

        navigation_layout = QHBoxLayout()
        navigation_layout.setSpacing(10)

        self._back_button = QPushButton("Back")
        self._back_button.setObjectName("secondaryActionButton")
        self._back_button.clicked.connect(self._go_back)

        navigation_layout.addWidget(self._back_button)
        navigation_layout.addStretch(1)

        self._title = QLabel()
        self._title.setObjectName("pageTitle")

        self._subtitle = QLabel()
        self._subtitle.setObjectName("pageSubtitle")
        self._subtitle.setWordWrap(True)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(14)

        layout.addLayout(navigation_layout)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)
        layout.addWidget(self._cards_container)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _rebuild_cards(
        self,
        definitions: tuple[TestDescriptionDefinition, ...],
    ) -> None:
        """Replace the visible description cards."""

        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        for definition in definitions:
            self._cards_layout.addWidget(self._build_description_card(definition))

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

        title = QLabel(f"{definition.test_code} — {definition.title}")
        title.setObjectName("profileSectionTitle")

        category = QLabel(definition.category)
        category.setObjectName("fieldHint")

        description = QLabel(definition.description)
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        path = description_document_path(definition)

        status = QLabel("Available" if path.is_file() else "Test description not yet available")
        status.setObjectName("formStatus")
        status.setProperty(
            "status",
            "success" if path.is_file() else "neutral",
        )

        button = QPushButton("Open Description")
        button.setObjectName("primaryActionButton")
        button.setEnabled(path.is_file())

        button.clicked.connect(
            lambda checked=False, selected_definition=definition, document_path=path: (
                self._request_document(
                    selected_definition,
                    document_path,
                )
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
            self._page_route,
        )

    def _go_back(self) -> None:
        """Return to the page that opened this contextual description."""

        if self._return_route is None:
            return

        self.back_requested.emit(self._return_route)

    @staticmethod
    def _back_button_text(return_route: str) -> str:
        """Return a useful contextual Back-button label."""

        labels = {
            "workspace.audit_procedures": "Back to Audit Procedures",
            "workspace.results": "Back to Results",
        }

        return labels.get(return_route, "Back")
