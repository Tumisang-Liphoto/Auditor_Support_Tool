"""Reusable placeholder page for upcoming application functions."""

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class PlaceholderPage(QWidget):
    """Page displayed while a feature is under development."""

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title = title
        self._build_interface(description)

    @property
    def title(self) -> str:
        """Return the page title."""

        return self._title

    def _build_interface(self, description: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel(self._title)
        title.setObjectName("pageTitle")

        subtitle = QLabel(description)
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        card = QFrame()
        card.setObjectName("card")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(8)

        card_title = QLabel("Development Status")
        card_title.setObjectName("cardTitle")

        card_status = QLabel("Application foundation completed")
        card_status.setObjectName("cardStatus")

        card_text = QLabel(
            "This page has been connected to the application navigation. "
            "Its detailed controls and business logic will be added during "
            "the relevant development milestone."
        )
        card_text.setObjectName("cardText")
        card_text.setWordWrap(True)

        card_layout.addWidget(card_title)
        card_layout.addWidget(card_status)
        card_layout.addWidget(card_text)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(card)
        layout.addStretch()
