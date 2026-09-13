"""Embedded PDF viewer for one complete audit procedure report."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.audit_procedure_report_builder import AuditProcedureReportBuilder
from auditor_support_tool.core.audit_procedure_report_models import AuditProcedureReport
from auditor_support_tool.presentation.report_export_document import ReportExportRequest
from auditor_support_tool.services.audit_export_service import AuditExportError, AuditExportService


class AuditProcedureReportDialog(QDialog):
    """Generate a temporary PDF and display it inside the application."""

    _MIN_ZOOM = 0.25
    _MAX_ZOOM = 4.0
    _ZOOM_STEP = 1.2

    def __init__(
        self,
        *,
        request: ReportExportRequest,
        parent: QWidget | None = None,
        export_service: AuditExportService | None = None,
    ) -> None:
        super().__init__(parent)

        self._request = request
        self._report = AuditProcedureReportBuilder().build(
            definition=request.definition,
            result=request.result,
        )
        self._export_service = export_service or AuditExportService()
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="auditor-support-report-preview-"
        )
        self._preview_path = Path(self._temporary_directory.name) / "audit-procedure-report.pdf"
        self._preview_error = ""

        self.setWindowTitle(f"{self._report.identity.display_id} Audit Procedure Report")
        self.setModal(True)
        self.resize(1240, 820)
        self.setMinimumSize(900, 620)

        self._document = QPdfDocument(self)
        self._pdf_bytes = QByteArray()
        self._pdf_buffer = QBuffer(self)
        self._build_interface()
        self._load_preview()

    @property
    def report(self) -> AuditProcedureReport:
        """Return the authoritative structured report represented by the PDF."""

        return self._report

    @property
    def preview_path(self) -> Path:
        """Return the temporary PDF path while the viewer is open."""

        return self._preview_path

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("profileSectionCard")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        toolbar_layout.setSpacing(8)

        self._previous_button = QPushButton("Previous")
        self._previous_button.setObjectName("secondaryActionButton")
        self._previous_button.clicked.connect(self._previous_page)

        self._next_button = QPushButton("Next")
        self._next_button.setObjectName("secondaryActionButton")
        self._next_button.clicked.connect(self._next_page)

        self._page_label = QLabel("Page 0 of 0")
        self._page_label.setObjectName("fieldHint")
        self._page_label.setMinimumWidth(100)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._zoom_out_button = QPushButton("Zoom -")
        self._zoom_out_button.setObjectName("secondaryActionButton")
        self._zoom_out_button.clicked.connect(lambda: self._change_zoom(1 / self._ZOOM_STEP))

        self._zoom_in_button = QPushButton("Zoom +")
        self._zoom_in_button.setObjectName("secondaryActionButton")
        self._zoom_in_button.clicked.connect(lambda: self._change_zoom(self._ZOOM_STEP))

        self._fit_width_button = QPushButton("Fit Width")
        self._fit_width_button.setObjectName("secondaryActionButton")
        self._fit_width_button.clicked.connect(
            lambda: self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        )

        self._fit_page_button = QPushButton("Fit Page")
        self._fit_page_button.setObjectName("secondaryActionButton")
        self._fit_page_button.clicked.connect(
            lambda: self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitInView)
        )

        close_button = QPushButton("Close")
        close_button.setObjectName("primaryActionButton")
        close_button.clicked.connect(self.accept)

        toolbar_layout.addWidget(self._previous_button)
        toolbar_layout.addWidget(self._next_button)
        toolbar_layout.addWidget(self._page_label)
        toolbar_layout.addSpacing(12)
        toolbar_layout.addWidget(self._zoom_out_button)
        toolbar_layout.addWidget(self._zoom_in_button)
        toolbar_layout.addWidget(self._fit_width_button)
        toolbar_layout.addWidget(self._fit_page_button)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(close_button)

        self._status_label = QLabel("Preparing PDF report preview…")
        self._status_label.setObjectName("profileSectionDescription")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setContentsMargins(24, 24, 24, 24)

        self._pdf_view = QPdfView()
        self._pdf_view.setObjectName("auditProcedurePdfView")
        self._pdf_view.setDocument(self._document)
        self._pdf_view.setPageMode(QPdfView.PageMode.MultiPage)
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self._pdf_view.setVisible(False)

        self._navigator = self._pdf_view.pageNavigator()
        self._navigator.currentPageChanged.connect(self._update_page_controls)

        root_layout.addWidget(toolbar)
        root_layout.addWidget(self._status_label)
        root_layout.addWidget(self._pdf_view, 1)

        self._set_navigation_enabled(False)

    def _load_preview(self) -> None:
        try:
            self._export_service.export_report(self._request, self._preview_path, "pdf")
            self._pdf_bytes = QByteArray(self._preview_path.read_bytes())
            self._pdf_buffer.setData(self._pdf_bytes)
            if not self._pdf_buffer.open(QIODevice.OpenModeFlag.ReadOnly):
                raise OSError("The generated PDF preview could not be opened in memory.")
            self._document.load(self._pdf_buffer)
        except AuditExportError as error:
            self._show_preview_error(str(error))
            return
        except Exception:
            self._show_preview_error(
                "The PDF report preview could not be opened. No audit data was changed."
            )
            return

        if (
            self._document.error() != QPdfDocument.Error.None_
            or self._document.pageCount() <= 0
        ):
            self._show_preview_error(
                "The PDF report preview could not be opened. No audit data was changed."
            )
            return

        self._status_label.setVisible(False)
        self._pdf_view.setVisible(True)
        self._set_navigation_enabled(True)
        self._update_page_controls()

    def _show_preview_error(self, message: str) -> None:
        self._preview_error = message
        self._status_label.setText(f"Report preview unavailable.\n\n{message}")
        self._status_label.setVisible(True)
        self._pdf_view.setVisible(False)
        self._set_navigation_enabled(False)

    def _set_navigation_enabled(self, enabled: bool) -> None:
        self._previous_button.setEnabled(enabled)
        self._next_button.setEnabled(enabled)
        self._zoom_out_button.setEnabled(enabled)
        self._zoom_in_button.setEnabled(enabled)
        self._fit_width_button.setEnabled(enabled)
        self._fit_page_button.setEnabled(enabled)

    def _update_page_controls(self, *_args) -> None:
        page_count = self._document.pageCount()
        current_page = self._navigator.currentPage() if page_count else -1
        display_page = current_page + 1 if current_page >= 0 else 0
        self._page_label.setText(f"Page {display_page} of {page_count}")
        self._previous_button.setEnabled(page_count > 0 and current_page > 0)
        self._next_button.setEnabled(page_count > 0 and current_page < page_count - 1)

    def _previous_page(self) -> None:
        current_page = self._navigator.currentPage()
        if current_page > 0:
            self._navigator.jump(current_page - 1, QPointF(), 0)

    def _next_page(self) -> None:
        current_page = self._navigator.currentPage()
        if 0 <= current_page < self._document.pageCount() - 1:
            self._navigator.jump(current_page + 1, QPointF(), 0)

    def _change_zoom(self, multiplier: float) -> None:
        current = self._pdf_view.zoomFactor()
        target = min(self._MAX_ZOOM, max(self._MIN_ZOOM, current * multiplier))
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.setZoomFactor(target)

    def done(self, result: int) -> None:
        """Release preview resources and remove the temporary report on close."""

        self._pdf_view.setDocument(None)
        self._document.close()
        self._pdf_buffer.close()
        self._pdf_bytes.clear()
        try:
            self._temporary_directory.cleanup()
        except OSError:
            # Closing the dialog must not fail if Windows delays filesystem cleanup.
            pass
        super().done(result)
