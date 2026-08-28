"""Generic readiness checks for audit procedures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.procedure_dataset_resolution import (
    ProcedureDatasetResolution,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.workbook_package import DatasetType


class ProcedureReadinessStatus(StrEnum):
    """Execution readiness of an audit procedure."""

    READY = "ready"
    READY_WITH_WARNING = "ready_with_warning"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ProcedureDatasetReadiness:
    """Field readiness for one resolved dataset role."""

    role: str
    dataset_type: DatasetType
    dataset_id: str | None

    mapped_required_fields: tuple[str, ...]
    missing_required_fields: tuple[str, ...]

    mapped_helpful_fields: tuple[str, ...]
    missing_helpful_fields: tuple[str, ...]

    resolution_reason: str = ""

    @property
    def resolved(self) -> bool:
        """Return whether a concrete dataset was supplied for this role."""

        return self.dataset_id is not None


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
    dataset_readiness: tuple[ProcedureDatasetReadiness, ...] = ()
    missing_required_datasets: tuple[str, ...] = ()

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

    def check_datasets(
        self,
        *,
        definition: ProcedureDefinition,
        resolution: ProcedureDatasetResolution,
    ) -> ProcedureReadiness:
        """Return readiness for a dataset-aware procedure resolution."""

        if not definition.dataset_requirements:
            raise ValueError("Dataset-aware readiness requires dataset requirements.")

        if resolution.procedure_id != definition.procedure_id:
            raise ValueError(
                "Dataset resolution procedure identifier does not match the definition."
            )

        dataset_readiness: list[ProcedureDatasetReadiness] = []
        missing_required_datasets: list[str] = []
        mapped_required_fields: list[str] = []
        missing_required_fields: list[str] = []
        mapped_helpful_fields: list[str] = []
        missing_helpful_fields: list[str] = []
        warnings: list[str] = []

        for resolved_dataset in resolution.datasets:
            requirement = resolved_dataset.requirement
            role = requirement.role

            if resolved_dataset.source is None:
                missing_required_datasets.append(role)
                dataset_readiness.append(
                    ProcedureDatasetReadiness(
                        role=role,
                        dataset_type=requirement.dataset_type,
                        dataset_id=None,
                        mapped_required_fields=(),
                        missing_required_fields=requirement.required_fields,
                        mapped_helpful_fields=(),
                        missing_helpful_fields=requirement.helpful_fields,
                        resolution_reason=resolved_dataset.reason,
                    )
                )
                continue

            source = resolved_dataset.source.source

            role_mapped_required = tuple(
                field_key
                for field_key in requirement.required_fields
                if source.has_field(field_key)
            )
            role_missing_required = tuple(
                field_key
                for field_key in requirement.required_fields
                if not source.has_field(field_key)
            )
            role_mapped_helpful = tuple(
                field_key for field_key in requirement.helpful_fields if source.has_field(field_key)
            )
            role_missing_helpful = tuple(
                field_key
                for field_key in requirement.helpful_fields
                if not source.has_field(field_key)
            )

            mapped_required_fields.extend(
                f"{role}.{field_key}" for field_key in role_mapped_required
            )
            missing_required_fields.extend(
                f"{role}.{field_key}" for field_key in role_missing_required
            )
            mapped_helpful_fields.extend(f"{role}.{field_key}" for field_key in role_mapped_helpful)
            missing_helpful_fields.extend(
                f"{role}.{field_key}" for field_key in role_missing_helpful
            )

            if requirement.helpful_fields and not role_mapped_helpful:
                warnings.append(
                    f"The {role} dataset has none of its helpful supporting fields mapped."
                )

            dataset_readiness.append(
                ProcedureDatasetReadiness(
                    role=role,
                    dataset_type=requirement.dataset_type,
                    dataset_id=source.dataset_id,
                    mapped_required_fields=role_mapped_required,
                    missing_required_fields=role_missing_required,
                    mapped_helpful_fields=role_mapped_helpful,
                    missing_helpful_fields=role_missing_helpful,
                )
            )

        if missing_required_datasets or missing_required_fields:
            status = ProcedureReadinessStatus.BLOCKED
        elif warnings:
            status = ProcedureReadinessStatus.READY_WITH_WARNING
        else:
            status = ProcedureReadinessStatus.READY

        return ProcedureReadiness(
            procedure_id=definition.procedure_id,
            status=status,
            mapped_required_fields=tuple(mapped_required_fields),
            missing_required_fields=tuple(missing_required_fields),
            mapped_helpful_fields=tuple(mapped_helpful_fields),
            missing_helpful_fields=tuple(missing_helpful_fields),
            warnings=tuple(warnings),
            dataset_readiness=tuple(dataset_readiness),
            missing_required_datasets=tuple(missing_required_datasets),
        )
