"""Resolve procedure dataset requirements against prepared workspace sources."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from auditor_support_tool.core.audit_record_source import AuditRecordSource
from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.workbook_package import DatasetType


@dataclass(frozen=True, slots=True)
class ProcedureDatasetSource:
    """One prepared audit source together with its confirmed dataset type."""

    dataset_type: DatasetType
    source: AuditRecordSource

    @classmethod
    def create(
        cls,
        *,
        dataset_type: DatasetType,
        source: AuditRecordSource,
    ) -> ProcedureDatasetSource:
        """Create one validated dataset source candidate."""

        if not isinstance(dataset_type, DatasetType):
            raise TypeError("Dataset source type must be a DatasetType.")

        if dataset_type == DatasetType.UNCLASSIFIED:
            raise ValueError("An unclassified dataset cannot satisfy a procedure requirement.")

        return cls(
            dataset_type=dataset_type,
            source=source,
        )


@dataclass(frozen=True, slots=True)
class ResolvedProcedureDataset:
    """Resolution result for one declared procedure dataset role."""

    requirement: ProcedureDatasetRequirement
    source: ProcedureDatasetSource | None = None
    reason: str = ""

    @property
    def resolved(self) -> bool:
        """Return whether exactly one suitable dataset source was resolved."""

        return self.source is not None


@dataclass(frozen=True, slots=True)
class ProcedureDatasetResolution:
    """Complete dataset-role resolution for one audit procedure."""

    procedure_id: str
    datasets: tuple[ResolvedProcedureDataset, ...]

    @property
    def complete(self) -> bool:
        """Return whether every declared dataset role was resolved."""

        return bool(self.datasets) and all(dataset.resolved for dataset in self.datasets)

    @property
    def unresolved_roles(self) -> tuple[str, ...]:
        """Return dataset roles that could not be resolved safely."""

        return tuple(dataset.requirement.role for dataset in self.datasets if not dataset.resolved)

    @property
    def primary(self) -> ResolvedProcedureDataset | None:
        """Return the primary dataset resolution."""

        for dataset in self.datasets:
            if dataset.requirement.primary:
                return dataset

        return None

    def source_for_role(
        self,
        role: str,
    ) -> AuditRecordSource | None:
        """Return the audit record source resolved for one role."""

        cleaned_role = role.strip().lower()

        for dataset in self.datasets:
            if dataset.requirement.role != cleaned_role:
                continue

            if dataset.source is None:
                return None

            return dataset.source.source

        return None


class ProcedureDatasetResolver:
    """Resolve generic procedure dataset roles from mapped workspace sources."""

    def resolve(
        self,
        *,
        definition: ProcedureDefinition,
        active_source: ProcedureDatasetSource,
        available_sources: Iterable[ProcedureDatasetSource],
    ) -> ProcedureDatasetResolution:
        """Resolve every dataset requirement without guessing between candidates."""

        if not definition.dataset_requirements:
            raise ValueError("Dataset resolution requires a dataset-aware procedure definition.")

        candidates = self._deduplicate_sources(
            available_sources,
            active_source=active_source,
        )

        resolved: list[ResolvedProcedureDataset] = []

        for requirement in definition.dataset_requirements:
            if requirement.primary:
                resolved.append(
                    self._resolve_primary(
                        requirement=requirement,
                        active_source=active_source,
                    )
                )
                continue

            resolved.append(
                self._resolve_reference(
                    requirement=requirement,
                    candidates=candidates,
                )
            )

        return ProcedureDatasetResolution(
            procedure_id=definition.procedure_id,
            datasets=tuple(resolved),
        )

    @staticmethod
    def _resolve_primary(
        *,
        requirement: ProcedureDatasetRequirement,
        active_source: ProcedureDatasetSource,
    ) -> ResolvedProcedureDataset:
        """Resolve the procedure population from the actively selected dataset."""

        if active_source.dataset_type != requirement.dataset_type:
            return ResolvedProcedureDataset(
                requirement=requirement,
                reason=(
                    "The active dataset is not the required primary "
                    f"dataset type: {requirement.dataset_type.value}."
                ),
            )

        return ResolvedProcedureDataset(
            requirement=requirement,
            source=active_source,
        )

    @staticmethod
    def _resolve_reference(
        *,
        requirement: ProcedureDatasetRequirement,
        candidates: tuple[ProcedureDatasetSource, ...],
    ) -> ResolvedProcedureDataset:
        """Resolve one reference role only when the match is unambiguous."""

        matches = tuple(
            candidate
            for candidate in candidates
            if candidate.dataset_type == requirement.dataset_type
        )

        if not matches:
            return ResolvedProcedureDataset(
                requirement=requirement,
                reason=(
                    "No mapped dataset is available for required type "
                    f"{requirement.dataset_type.value}."
                ),
            )

        if len(matches) > 1:
            return ResolvedProcedureDataset(
                requirement=requirement,
                reason=(
                    "More than one mapped dataset is available for required "
                    f"type {requirement.dataset_type.value}; the source is ambiguous."
                ),
            )

        return ResolvedProcedureDataset(
            requirement=requirement,
            source=matches[0],
        )

    @staticmethod
    def _deduplicate_sources(
        sources: Iterable[ProcedureDatasetSource],
        *,
        active_source: ProcedureDatasetSource,
    ) -> tuple[ProcedureDatasetSource, ...]:
        """Return candidates once per stable dataset identifier."""

        by_dataset_id: dict[str, ProcedureDatasetSource] = {
            active_source.source.dataset_id: active_source,
        }

        for candidate in sources:
            by_dataset_id[candidate.source.dataset_id] = candidate

        return tuple(by_dataset_id[dataset_id] for dataset_id in sorted(by_dataset_id))
