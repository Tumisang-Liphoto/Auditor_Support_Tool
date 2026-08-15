"""Generic readiness checks for audit procedures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)


class ProcedureReadinessStatus(StrEnum):
    """Execution readiness of an audit procedure."""

    READY = "ready"
    READY_WITH_WARNING = "ready_with_warning"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ProcedureReadiness:
    """Result of checking a procedure against an audit record source."""

    procedure_id: str
    status: ProcedureReadinessStatus

    mapped_required_fields: tuple[str, ...]
    missing_required_fields: tuple[str, ...]

    mapped_helpful_fields: tuple[str, ...]
    missing_helpful_fields: tuple[str, ...]

    warnings: tuple[str, ...] = ()

    @property
    def can_run(self) -> bool:
        """Return whether the procedure may execute."""

        return self.status in {
            ProcedureReadinessStatus.READY,
            ProcedureReadinessStatus.READY_WITH_WARNING,
        }

    @property
    def needs_attention(self) -> bool:
        """Return whether the user should be shown a readiness issue."""

        return self.status != ProcedureReadinessStatus.READY


class ProcedureReadinessService:
    """Determine whether a procedure can run against a prepared source."""

    def check(
        self,
        *,
        definition: ProcedureDefinition,
        source: AuditRecordSource,
    ) -> ProcedureReadiness:
        """Return readiness without executing or materialising source records."""

        mapped_required_fields = tuple(
            field_key for field_key in definition.required_fields if source.has_field(field_key)
        )

        missing_required_fields = tuple(
            field_key for field_key in definition.required_fields if not source.has_field(field_key)
        )

        mapped_helpful_fields = tuple(
            field_key for field_key in definition.helpful_fields if source.has_field(field_key)
        )

        missing_helpful_fields = tuple(
            field_key for field_key in definition.helpful_fields if not source.has_field(field_key)
        )

        warnings: list[str] = []

        if missing_required_fields:
            status = ProcedureReadinessStatus.BLOCKED
        elif definition.helpful_fields and not mapped_helpful_fields:
            status = ProcedureReadinessStatus.READY_WITH_WARNING
            warnings.append(
                "The procedure can run, but none of its helpful supporting fields are available."
            )
        else:
            status = ProcedureReadinessStatus.READY

        return ProcedureReadiness(
            procedure_id=definition.procedure_id,
            status=status,
            mapped_required_fields=mapped_required_fields,
            missing_required_fields=missing_required_fields,
            mapped_helpful_fields=mapped_helpful_fields,
            missing_helpful_fields=missing_helpful_fields,
            warnings=tuple(warnings),
        )
