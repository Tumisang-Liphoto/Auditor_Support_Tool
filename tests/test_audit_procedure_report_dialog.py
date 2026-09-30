"""Embedded PDF report viewer behaviour."""

from decimal import Decimal

from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QPushButton

from auditor_support_tool.core.audit_procedure_report_builder import AuditProcedureReportBuilder
from auditor_support_tool.gui.dialogs.audit_procedure_report_dialog import (
    AuditProcedureReportDialog,
)
from auditor_support_tool.presentation.exception_source_records import ExceptionSourceRecords
from auditor_support_tool.presentation.report_export_document import ReportExportRequest
from tests.test_audit_procedure_report import _definition, _result


def _request() -> ReportExportRequest:
    result = _result()
    sources = ExceptionSourceRecords(
        ("Original Ref", "Value", "Narrative"),
        {
            (exception.source_record_id, exception.source_row_number): (
                f"REF-{index:03}",
                Decimal("12.340"),
                "Preview evidence",
            )
            for index, exception in enumerate(result.exception_records)
        },
        result.context.dataset_id,
        result.context.source_sha256,
    )
    return ReportExportRequest(
        _definition(),
        result,
        sources,
        "Annual review",
        "Example auditee",
        "Ledger",
        "Transactions",
    )


def test_report_viewer_renders_temporary_pdf_inside_application(qtbot):
    request = _request()
    expected = AuditProcedureReportBuilder().build(
        definition=request.definition,
        result=request.result,
    )

    widget = AuditProcedureReportDialog(request=request)
    qtbot.addWidget(widget)

    assert widget.report.to_json() == expected.to_json()
    assert widget.preview_path.exists()
    assert widget.preview_path.suffix == ".pdf"
    assert widget._preview_error == ""
    assert widget._document.pageCount() > 0
    assert widget.findChild(QPdfView, "auditProcedurePdfView") is widget._pdf_view
    assert widget._pdf_view.isVisible() is False  # The modal dialog has not been shown yet.
    assert widget._page_label.text().startswith("Page 1 of ")
    assert not any("Export" in button.text() for button in widget.findChildren(QPushButton))

    preview_path = widget.preview_path
    widget.reject()
    assert not preview_path.exists()
