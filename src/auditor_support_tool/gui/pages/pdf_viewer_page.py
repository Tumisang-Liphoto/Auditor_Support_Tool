"""Shared embedded PDF document viewer."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PdfViewerPage(QWidget):
    """Display a PDF document inside the application."""

    back_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._return_route = "about.test_descriptions"

        self._document = QPdfDocument(self)
        self._viewer = QPdfView()
        self._title_label = QLabel()
        self._subtitle_label = QLabel()
        self._status_label = QLabel()
        self._back_button = QPushButton()

        self._build_interface()

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(40, 32, 40, 32)
        root_layout.setSpacing(14)

        heading_layout = QHBoxLayout()
        heading_layout.setSpacing(16)

        heading_text_layout = QVBoxLayout()
        heading_text_layout.setSpacing(4)

        self._title_label.setObjectName("pageTitle")

        self._subtitle_label.setObjectName("pageSubtitle")
        self._subtitle_label.setWordWrap(True)

        self._back_button.setText("Back to Documents")
        self._back_button.setObjectName("secondaryActionButton")
        self._back_button.clicked.connect(self._go_back)

        heading_text_layout.addWidget(self._title_label)
        heading_text_layout.addWidget(self._subtitle_label)

        heading_layout.addLayout(heading_text_layout, 1)
        heading_layout.addWidget(self._back_button)

        toolbar = QFrame()
        toolbar.setObjectName("profileSectionCard")

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 10)
        toolbar_layout.setSpacing(10)

        self._status_label.setObjectName("formStatus")
        self._status_label.setProperty("status", "neutral")

        zoom_out_button = QPushButton("Zoom Out")
        zoom_out_button.setObjectName("secondaryActionButton")
        zoom_out_button.clicked.connect(self._zoom_out)

        zoom_in_button = QPushButton("Zoom In")
        zoom_in_button.setObjectName("secondaryActionButton")
        zoom_in_button.clicked.connect(self._zoom_in)

        fit_width_button = QPushButton("Fit Width")
        fit_width_button.setObjectName("secondaryActionButton")
        fit_width_button.clicked.connect(self._fit_width)

        toolbar_layout.addWidget(self._status_label, 1)
        toolbar_layout.addWidget(zoom_out_button)
        toolbar_layout.addWidget(zoom_in_button)
        toolbar_layout.addWidget(fit_width_button)

        self._viewer.setObjectName("pdfDocumentViewer")
        self._viewer.setDocument(self._document)
        self._viewer.setPageMode(QPdfView.PageMode.MultiPage)
        self._viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        root_layout.addLayout(heading_layout)
        root_layout.addWidget(toolbar)
        root_layout.addWidget(self._viewer, 1)

    def open_document(
        self,
        *,
        path: Path,
        title: str,
        subtitle: str,
        return_route: str,
    ) -> bool:
        """Load and display a PDF document."""

        self.close_document()

        self._return_route = return_route

        if return_route == "about.manuals":
            self._back_button.setText("Back to Manuals")
        else:
            self._back_button.setText("Back to Test Descriptions")
        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)

        if not path.is_file():
            self._set_status(
                f"Document not found: {path.name}",
                "error",
            )
            return False

        error = self._document.load(str(path.resolve()))

        if error != QPdfDocument.Error.None_:
            self._set_status(
                f"Unable to load PDF: {error.name}",
                "error",
            )
            return False

        self._viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)

        self._set_status(
            f"Document loaded | {self._document.pageCount()} page(s)",
            "success",
        )

        return True

    def close_document(self) -> None:
        """Unload the current PDF and release its resources."""

        self._document.close()
        self._title_label.clear()
        self._subtitle_label.clear()

        self._set_status(
            "No document loaded",
            "neutral",
        )

    def _go_back(self) -> None:
        """Return to the page that opened the document."""

        self.back_requested.emit(self._return_route)

    def _zoom_in(self) -> None:
        """Increase the PDF zoom level."""

        self._viewer.setZoomMode(QPdfView.ZoomMode.Custom)

        self._viewer.setZoomFactor(
            min(
                self._viewer.zoomFactor() + 0.15,
                4.0,
            )
        )

    def _zoom_out(self) -> None:
        """Reduce the PDF zoom level."""

        self._viewer.setZoomMode(QPdfView.ZoomMode.Custom)

        self._viewer.setZoomFactor(
            max(
                self._viewer.zoomFactor() - 0.15,
                0.25,
            )
        )

    def _fit_width(self) -> None:
        """Fit the PDF page to the viewer width."""

        self._viewer.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _set_status(
        self,
        message: str,
        status: str,
    ) -> None:
        """Update the viewer status message."""

        self._status_label.setText(message)
        self._status_label.setProperty("status", status)

        style = self._status_label.style()
        style.unpolish(self._status_label)
        style.polish(self._status_label)
        self._status_label.update()