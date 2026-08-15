"""Outcome models for generic Test Engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionOutcome,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
)
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadiness,
)


class TestEngineStatus(StrEnum):
    """High-level outcome of one Test Engine request."""

    NOT_IMPLEMENTED = "not_implemented"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TestEngineOutcome:
    """Complete high-level outcome returned by the Test Engine."""

    procedure_id: str
    dataset_id: str
    status: TestEngineStatus

    readiness: ProcedureReadiness | None = None
    execution: AuditExecutionOutcome | None = None
    result: ProcedureResult | None = None

    error_message: str = ""

    @property
    def completed(self) -> bool:
        """Return whether the procedure completed successfully."""

        return self.status == TestEngineStatus.COMPLETED

    @property
    def was_executed(self) -> bool:
        """Return whether the request reached the execution service."""

        return self.execution is not None

    @property
    def has_result(self) -> bool:
        """Return whether a standard procedure result is available."""

        return self.result is not None
