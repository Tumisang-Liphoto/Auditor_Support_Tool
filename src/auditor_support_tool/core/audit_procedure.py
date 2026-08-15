"""Generic executable audit-procedure contract."""

from __future__ import annotations

from typing import Protocol

from auditor_support_tool.core.audit_execution_models import (
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)


class AuditProcedure(Protocol):
    """Executable implementation of one audit procedure."""

    @property
    def definition(self) -> ProcedureDefinition:
        """Return the authoritative definition for this procedure."""

        ...

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        """Execute the procedure and return its standard result."""

        ...
