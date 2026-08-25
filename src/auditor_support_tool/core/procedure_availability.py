"""Determine which registered audit procedures are usable for a dataset."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadiness,
    ProcedureReadinessService,
)


class ExecutableProcedure(Protocol):
    """Minimum executable-procedure contract required for availability checks."""

    @property
    def definition(self) -> ProcedureDefinition:
        """Return the procedure definition."""


@dataclass(frozen=True, slots=True)
class AvailableProcedure:
    """One implemented procedure that can run on the supplied data."""

    procedure: ExecutableProcedure
    readiness: ProcedureReadiness


class ProcedureAvailabilityService:
    """Filter implemented procedures using the normal readiness rules."""

    def __init__(
        self,
        *,
        readiness_service: ProcedureReadinessService | None = None,
    ) -> None:
        self._readiness_service = readiness_service or ProcedureReadinessService()

    def available(
        self,
        *,
        procedures: Iterable[ExecutableProcedure],
        source: AuditRecordSource,
    ) -> tuple[AvailableProcedure, ...]:
        """Return only procedures whose required data is available."""

        available: list[AvailableProcedure] = []

        for procedure in procedures:
            readiness = self._readiness_service.check(
                definition=procedure.definition,
                source=source,
            )

            if not readiness.can_run:
                continue

            available.append(
                AvailableProcedure(
                    procedure=procedure,
                    readiness=readiness,
                )
            )

        return tuple(available)
