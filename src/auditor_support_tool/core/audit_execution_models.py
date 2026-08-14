"""Execution models and cancellation primitives for audit procedures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from threading import Event
from uuid import uuid4

from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)
from auditor_support_tool.core.workspace_models import utc_now_iso


class AuditExecutionStatus(StrEnum):
    """Lifecycle status for one audit-procedure execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AuditExecutionRequest:
    """Identity and audit context for one procedure execution."""

    execution_id: str
    procedure_id: str
    dataset_id: str
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        procedure_id: str,
        dataset_id: str,
    ) -> AuditExecutionRequest:
        """Create a validated procedure-execution request."""

        cleaned_procedure_id = procedure_id.strip()
        cleaned_dataset_id = dataset_id.strip()

        if not cleaned_procedure_id:
            raise ValueError("Procedure identifier is required.")

        if not cleaned_dataset_id:
            raise ValueError("Dataset identifier is required.")

        canonical_id = canonical_procedure_id(cleaned_procedure_id)

        return cls(
            execution_id=str(uuid4()),
            procedure_id=canonical_id,
            dataset_id=cleaned_dataset_id,
            created_at=utc_now_iso(),
        )

    @property
    def execution_key(self) -> str:
        """Return the key used to prevent conflicting duplicate execution."""

        return f"{self.procedure_id}:{self.dataset_id}"


@dataclass(frozen=True, slots=True)
class AuditExecutionOutcome:
    """Recorded outcome of one audit-procedure execution."""

    request: AuditExecutionRequest
    status: AuditExecutionStatus
    started_at: str
    finished_at: str
    duration_seconds: float
    source_record_count: int
    payload: object | None = None
    error_message: str = ""


@dataclass(slots=True)
class ExecutionCancellationToken:
    """Thread-safe cancellation token shared with a running procedure."""

    _event: Event = field(
        default_factory=Event,
        init=False,
        repr=False,
    )

    def cancel(self) -> None:
        """Request cancellation of the running procedure."""

        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""

        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise a controlled exception when cancellation was requested."""

        if self.is_cancelled:
            raise AuditExecutionCancelledError("Audit procedure execution was cancelled.")


class AuditExecutionCancelledError(RuntimeError):
    """Raised cooperatively by a procedure after cancellation is requested."""
