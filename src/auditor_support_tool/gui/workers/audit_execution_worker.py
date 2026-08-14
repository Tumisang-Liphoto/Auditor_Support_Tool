"""Background worker for guarded audit-procedure execution."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionOutcome,
    AuditExecutionRequest,
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_execution_service import (
    AuditExecutionService,
    AuditProcedureRunner,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
)


class AuditExecutionWorkerSignals(QObject):
    """Signals emitted by an audit execution worker."""

    started = Signal(str)
    finished = Signal(object)
    failed = Signal(str)


class AuditExecutionWorker(QRunnable):
    """Run one audit procedure away from the GUI thread."""

    def __init__(
        self,
        *,
        execution_service: AuditExecutionService,
        request: AuditExecutionRequest,
        table: LoadedTable,
        runner: AuditProcedureRunner,
    ) -> None:
        super().__init__()

        self._execution_service = execution_service
        self._request = request
        self._table = table
        self._runner = runner
        self._cancellation_token = ExecutionCancellationToken()

        self.signals = AuditExecutionWorkerSignals()

    @property
    def cancellation_token(self) -> ExecutionCancellationToken:
        """Return the token supplied to the procedure runner."""

        return self._cancellation_token

    def cancel(self) -> None:
        """Request cooperative cancellation."""

        self._cancellation_token.cancel()

    @Slot()
    def run(self) -> None:
        """Execute the procedure and emit its final outcome."""

        self.signals.started.emit(self._request.execution_id)

        try:
            outcome: AuditExecutionOutcome = self._execution_service.execute(
                request=self._request,
                table=self._table,
                runner=self._runner,
                cancellation_token=self._cancellation_token,
            )
        except Exception as error:
            self.signals.failed.emit(str(error))
            return

        self.signals.finished.emit(outcome)
