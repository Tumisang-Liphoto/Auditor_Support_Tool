"""Run the complete generic Test Engine pipeline outside the GUI thread."""

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QThread, Slot

from auditor_support_tool.core.audit_execution_models import ExecutionCancellationToken
from auditor_support_tool.core.audit_record_source import AuditRecordSource
from auditor_support_tool.core.procedure_dataset_resolution import ProcedureDatasetSource
from auditor_support_tool.core.procedure_execution_status_service import (
    ProcedureExecutionStatusService,
)
from auditor_support_tool.core.test_engine_models import TestEngineOutcome, TestEngineStatus
from auditor_support_tool.core.test_engine_service import TestEngineService


class AuditExecutionWorker(QThread):
    """Own one run until the thread finishes, even if its page is destroyed."""

    _active: set = set()

    def __init__(
        self,
        *,
        engine: TestEngineService,
        procedure_id: str,
        source: AuditRecordSource,
        source_path: Path,
        audit_period_start: str,
        audit_period_end: str,
        parameters: dict[str, object],
        dataset_sources: tuple[ProcedureDatasetSource, ...],
        status_service: ProcedureExecutionStatusService,
    ) -> None:
        super().__init__(QCoreApplication.instance())
        self._engine = engine
        self._inputs = dict(
            procedure_id=procedure_id,
            source=source,
            source_path=source_path,
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            parameters=deepcopy(parameters),
            dataset_sources=dataset_sources,
        )
        self._status_service = status_service
        self.cancellation_token = ExecutionCancellationToken()
        self.outcome: TestEngineOutcome | None = None
        self.finished.connect(self._release)

    def start(self) -> None:
        self._active.add(self)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._shutdown)
        super().start()

    @Slot()
    def cancel(self) -> None:
        self.cancellation_token.cancel()

    @Slot()
    def _shutdown(self) -> None:
        self.cancel()
        self.wait()

    @Slot()
    def _release(self) -> None:
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.disconnect(self._shutdown)
        self._active.discard(self)
        self.deleteLater()

    def run(self) -> None:
        try:
            self.outcome = self._engine.run(
                **self._inputs,
                cancellation_token=self.cancellation_token,
            )
        except Exception:
            self.outcome = TestEngineOutcome(
                procedure_id=self._inputs["procedure_id"],
                dataset_id=self._inputs["source"].dataset_id,
                status=TestEngineStatus.FAILED,
                error_message="The audit procedure could not be completed.",
            )
        if self.outcome.status == TestEngineStatus.COMPLETED:
            try:
                # Verify current bytes independently of authoritative run evidence.
                self._status_service.refresh_source_hash(self._inputs["source_path"])
            except Exception:
                # Optional cache failure cannot erase a valid completed result.
                pass
