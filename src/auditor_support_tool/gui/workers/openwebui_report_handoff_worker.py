"""Background worker for sending an audit procedure report to OpenWebUI."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReport,
)
from auditor_support_tool.services.audit_report_ai_handoff import (
    AuditReportAIHandoffService,
)


class OpenWebUIReportHandoffWorker(QThread):
    """Upload and analyse an audit report without blocking the interface."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        *,
        service: AuditReportAIHandoffService,
        report: AuditProcedureReport,
    ) -> None:
        super().__init__()

        self._service = service
        self._report = report

    def run(self) -> None:
        """Send the report and emit the persistent OpenWebUI chat."""

        try:
            result = self._service.send_report(self._report)
        except Exception as error:
            self.failed.emit(str(error))
            return

        self.completed.emit(result)
