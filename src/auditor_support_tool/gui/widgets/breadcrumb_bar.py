"""Reusable application breadcrumb navigation display."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)


class BreadcrumbBar(QWidget):
    """Display the current application navigation hierarchy."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("breadcrumbBar")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self._layout.setSpacing(7)

        self.set_parts(("Dashboard",))

    def set_parts(
        self,
        parts: Sequence[str],
    ) -> None:
        """Replace the displayed breadcrumb hierarchy."""

        self._clear()

        clean_parts = tuple(part.strip() for part in parts if part.strip())

        if not clean_parts:
            clean_parts = ("Dashboard",)

        last_index = len(clean_parts) - 1

        for index, part in enumerate(clean_parts):
            label = QLabel(part)

            if index == last_index:
                label.setObjectName("breadcrumbCurrent")
            else:
                label.setObjectName("breadcrumbRoot")

            self._layout.addWidget(label)

            if index < last_index:
                separator = QLabel("›")
                separator.setObjectName("breadcrumbSeparator")
                self._layout.addWidget(separator)

        self._layout.addStretch(1)

    def _clear(self) -> None:
        """Remove current breadcrumb widgets."""

        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
