"""Determine which registered audit procedures are usable for mapped data."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from auditor_support_tool.core.audit_record_source import AuditRecordSource
from auditor_support_tool.core.procedure_dataset_resolution import (
    ProcedureDatasetResolution,
    ProcedureDatasetResolver,
    ProcedureDatasetSource,
)
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
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
    dataset_resolution: ProcedureDatasetResolution | None = None


class ProcedureAvailabilityService:
    """Filter implemented procedures using generic readiness rules."""

    def __init__(
        self,
        *,
        readiness_service: ProcedureReadinessService | None = None,
        dataset_resolver: ProcedureDatasetResolver | None = None,
    ) -> None:
        self._readiness_service = readiness_service or ProcedureReadinessService()
        self._dataset_resolver = dataset_resolver or ProcedureDatasetResolver()

    def available(
        self,
        *,
        procedures: Iterable[ExecutableProcedure],
        source: AuditRecordSource,
    ) -> tuple[AvailableProcedure, ...]:
        """Return legacy single-dataset procedures runnable on one source."""

        available: list[AvailableProcedure] = []

        for procedure in procedures:
            if procedure.definition.uses_dataset_requirements:
                continue

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

    def available_for_workspace(
        self,
        *,
        procedures: Iterable[ExecutableProcedure],
        active_source: ProcedureDatasetSource,
        mapped_sources: Iterable[ProcedureDatasetSource],
    ) -> tuple[AvailableProcedure, ...]:
        """Return procedures runnable with the active and mapped workspace data."""

        available: list[AvailableProcedure] = []

        mapped_sources_tuple = tuple(mapped_sources)

        for procedure in procedures:
            definition = procedure.definition

            if not definition.uses_dataset_requirements:
                readiness = self._readiness_service.check(
                    definition=definition,
                    source=active_source.source,
                )

                if readiness.can_run:
                    available.append(
                        AvailableProcedure(
                            procedure=procedure,
                            readiness=readiness,
                        )
                    )

                continue

            resolution = self._dataset_resolver.resolve(
                definition=definition,
                active_source=active_source,
                available_sources=mapped_sources_tuple,
            )
            readiness = self._readiness_service.check_datasets(
                definition=definition,
                resolution=resolution,
            )

            if not readiness.can_run:
                continue

            available.append(
                AvailableProcedure(
                    procedure=procedure,
                    readiness=readiness,
                    dataset_resolution=resolution,
                )
            )

        return tuple(available)
