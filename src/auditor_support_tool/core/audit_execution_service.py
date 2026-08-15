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
from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.workspace_models import utc_now_iso

AuditProcedureRunner = Callable[
    [AuditRecordSource, ExecutionCancellationToken],
    object,
]


class AuditExecutionConflictError(RuntimeError):
    """Raised when the same procedure/dataset pair is already running."""


class AuditExecutionSourceError(RuntimeError):
    """Raised when an execution request does not match its record source."""


class AuditExecutionService:
    """Execute audit procedures with common safety and traceability rules."""

    def __init__(self) -> None:
        self._active_execution_keys: set[str] = set()
        self._active_lock = Lock()

    def execute(
        self,
        *,
        request: AuditExecutionRequest,
        source: AuditRecordSource,
        runner: AuditProcedureRunner,
        cancellation_token: ExecutionCancellationToken | None = None,
    ) -> AuditExecutionOutcome:
        """Execute one procedure against the complete audit record source.

        The supplied record source is passed directly to the procedure runner.
        The execution service does not sample, truncate, materialise or copy
        the source population.
        """

        if request.dataset_id != source.dataset_id:
            raise AuditExecutionSourceError(
                "Execution request dataset does not match the audit record source."
            )

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
                    source=source,
                )

            try:
                payload = runner(
                    source,
                    token,
                )
            except AuditExecutionCancelledError:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.CANCELLED,
                    started_at=started_at,
                    started_clock=started_clock,
                    source=source,
                )
            except Exception as error:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.FAILED,
                    started_at=started_at,
                    started_clock=started_clock,
                    source=source,
                    error_message=str(error),
                )

            if token.is_cancelled:
                return self._build_outcome(
                    request=request,
                    status=AuditExecutionStatus.CANCELLED,
                    started_at=started_at,
                    started_clock=started_clock,
                    source=source,
                    payload=payload,
                )

            return self._build_outcome(
                request=request,
                status=AuditExecutionStatus.COMPLETED,
                started_at=started_at,
                started_clock=started_clock,
                source=source,
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
        source: AuditRecordSource,
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
            source_record_count=source.record_count,
            payload=payload,
            error_message=error_message,
        )
