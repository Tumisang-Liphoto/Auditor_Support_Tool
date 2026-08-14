"""Guarded execution service for audit procedures."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from time import perf_counter

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionCancelledError,
    AuditExecutionOutcome,
    AuditExecutionRequest,
    AuditExecutionStatus,
    ExecutionCancellationToken,
)
from auditor_support_tool.core.data_models import LoadedTable
from auditor_support_tool.core.workspace_models import utc_now_iso

AuditProcedureRunner = Callable[
    [LoadedTable, ExecutionCancellationToken],
    object,
]


class AuditExecutionConflictError(RuntimeError):
    """Raised when the same procedure/dataset pair is already running."""


class AuditExecutionService:
    """Execute audit procedures with common safety and traceability rules."""

    def __init__(self) -> None:
        self._active_execution_keys: set[str] = set()
        self._active_lock = Lock()

    def execute(
        self,
        *,
        request: AuditExecutionRequest,
        table: LoadedTable,
        runner: AuditProcedureRunner,
        cancellation_token: ExecutionCancellationToken | None = None,
    ) -> AuditExecutionOutcome:
        """Execute one procedure against the complete loaded population.

        The supplied ``LoadedTable`` is passed directly to the procedure runner.
        This service does not sample, truncate or copy ``table.rows``.
        """

        token = cancellation_token or ExecutionCancellationToken()
        execution_key = request.execution_key

        self._register_execution(execution_key)

        started_at = utc_now_iso()
        started_clock = perf_counter()

        try:
            if token.is_cancelled:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.CANCELLED,
                    started_at=started_at,
                    started_clock=started_clock,
                    table=table,
                )

            try:
                payload = runner(
                    table,
                    token,
                )
            except AuditExecutionCancelledError:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.CANCELLED,
                    started_at=started_at,
                    started_clock=started_clock,
                    table=table,
                )
            except Exception as error:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.FAILED,
                    started_at=started_at,
                    started_clock=started_clock,
                    table=table,
                    error_message=str(error),
                )

            if token.is_cancelled:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.CANCELLED,
                    started_at=started_at,
                    started_clock=started_clock,
                    table=table,
                    payload=payload,
                )

            return self._build_outcome(
                request=request,
                status=AuditExecutionStatus.COMPLETED,
                started_at=started_at,
                started_clock=started_clock,
                table=table,
                payload=payload,
            )

        finally:
            self._release_execution(execution_key)

    def is_running(
        self,
        *,
        procedure_id: str,
        dataset_id: str,
    ) -> bool:
        """Return whether the procedure/dataset pair is already executing."""

        execution_key = f"{procedure_id.strip()}:{dataset_id.strip()}"

        with self._active_lock:
            return execution_key in self._active_execution_keys

    def _register_execution(
        self,
        execution_key: str,
    ) -> None:
        """Register a procedure/dataset pair as actively executing."""

        with self._active_lock:
            if execution_key in self._active_execution_keys:
                raise AuditExecutionConflictError(
                    "This audit procedure is already running for the selected dataset."
                )

            self._active_execution_keys.add(execution_key)

    def _release_execution(
        self,
        execution_key: str,
    ) -> None:
        """Remove a completed execution from the active set."""

        with self._active_lock:
            self._active_execution_keys.discard(execution_key)

    @staticmethod
    def _build_outcome(
        *,
        request: AuditExecutionRequest,
        status: AuditExecutionStatus,
        started_at: str,
        started_clock: float,
        table: LoadedTable,
        payload: object | None = None,
        error_message: str = "",
    ) -> AuditExecutionOutcome:
        """Build the common execution outcome."""

        duration_seconds = max(
            0.0,
            perf_counter() - started_clock,
        )

        return AuditExecutionOutcome(
            request=request,
            status=status,
            started_at=started_at,
            finished_at=utc_now_iso(),
            duration_seconds=duration_seconds,
            source_record_count=table.record_count,
            payload=payload,
            error_message=error_message,
        )
