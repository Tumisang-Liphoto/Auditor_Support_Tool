"""Central workflow-readiness checks for an audit workspace."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from auditor_support_tool.core.workbook_package import (
    FieldMappingStatus,
    PreparationStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workspace_state import WorkspaceState


class WorkspaceStage(StrEnum):
    """Workflow stages whose availability depends on workspace state."""

    DATA_SOURCES = "data_sources"
    DATA_PROFILE = "data_profile"
    DATA_PREPARATION = "data_preparation"
    FIELD_MAPPING = "field_mapping"
    AUDIT_PROCEDURES = "audit_procedures"


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Outcome of checking whether a workflow stage is available."""

    stage: WorkspaceStage
    ready: bool
    message: str
    blockers: tuple[str, ...] = ()


class WorkspaceReadinessService:
    """Evaluate workspace progress without depending on GUI page logic."""

    _PREPARATION_COMPLETE = {
        PreparationStatus.CONFIRMED,
        PreparationStatus.CONFIRMED_WITH_WARNINGS,
    }

    _MAPPING_COMPLETE = {
        FieldMappingStatus.CONFIRMED,
        FieldMappingStatus.CONFIRMED_WITH_WARNINGS,
        FieldMappingStatus.NOT_APPLICABLE,
    }

    def check(
        self,
        state: WorkspaceState,
        stage: WorkspaceStage,
    ) -> ReadinessResult:
        """Return whether the requested workflow stage is currently available."""

        if stage == WorkspaceStage.DATA_SOURCES:
            return self._check_data_sources(state)

        if stage == WorkspaceStage.DATA_PROFILE:
            return self._check_data_profile(state)

        if stage == WorkspaceStage.DATA_PREPARATION:
            return self._check_data_preparation(state)

        if stage == WorkspaceStage.FIELD_MAPPING:
            return self._check_field_mapping(state)

        if stage == WorkspaceStage.AUDIT_PROCEDURES:
            return self._check_audit_procedures(state)

        raise ValueError(f"Unsupported workspace stage: {stage}")

    def can_access(
        self,
        state: WorkspaceState,
        stage: WorkspaceStage,
    ) -> bool:
        """Return only the readiness boolean for a workflow stage."""

        return self.check(state, stage).ready

    def _check_data_sources(
        self,
        state: WorkspaceState,
    ) -> ReadinessResult:
        if not state.has_workspace:
            return ReadinessResult(
                stage=WorkspaceStage.DATA_SOURCES,
                ready=False,
                message="Create or open an audit workspace first.",
                blockers=("No active audit workspace.",),
            )

        return ReadinessResult(
            stage=WorkspaceStage.DATA_SOURCES,
            ready=True,
            message="The workspace is ready for source-data selection.",
        )

    def _check_data_profile(
        self,
        state: WorkspaceState,
    ) -> ReadinessResult:
        workspace_check = self._check_data_sources(state)

        if not workspace_check.ready:
            return ReadinessResult(
                stage=WorkspaceStage.DATA_PROFILE,
                ready=False,
                message=workspace_check.message,
                blockers=workspace_check.blockers,
            )

        if not state.has_workbook_package:
            return ReadinessResult(
                stage=WorkspaceStage.DATA_PROFILE,
                ready=False,
                message="Load and analyse a source workbook first.",
                blockers=("No workbook package is loaded.",),
            )

        datasets = self._confirmed_source_datasets(state)

        if not datasets:
            return ReadinessResult(
                stage=WorkspaceStage.DATA_PROFILE,
                ready=False,
                message="Confirm at least one dataset in Data Sources first.",
                blockers=("No selected dataset has been confirmed in Data Sources.",),
            )

        return ReadinessResult(
            stage=WorkspaceStage.DATA_PROFILE,
            ready=True,
            message="Confirmed datasets are available for profile review.",
        )

    def _check_data_preparation(
        self,
        state: WorkspaceState,
    ) -> ReadinessResult:
        profile_check = self._check_data_profile(state)

        if not profile_check.ready:
            return ReadinessResult(
                stage=WorkspaceStage.DATA_PREPARATION,
                ready=False,
                message=profile_check.message,
                blockers=profile_check.blockers,
            )

        datasets = self._confirmed_source_datasets(state)

        missing_profiles = tuple(
            dataset.confirmed_display_name for dataset in datasets if dataset.data_profile is None
        )

        if missing_profiles:
            return ReadinessResult(
                stage=WorkspaceStage.DATA_PREPARATION,
                ready=False,
                message="Every confirmed dataset requires a data profile.",
                blockers=tuple(f"Missing data profile: {name}" for name in missing_profiles),
            )

        return ReadinessResult(
            stage=WorkspaceStage.DATA_PREPARATION,
            ready=True,
            message="All confirmed datasets are ready for Data Preparation.",
        )

    def _check_field_mapping(
        self,
        state: WorkspaceState,
    ) -> ReadinessResult:
        preparation_check = self._check_data_preparation(state)

        if not preparation_check.ready:
            return ReadinessResult(
                stage=WorkspaceStage.FIELD_MAPPING,
                ready=False,
                message=preparation_check.message,
                blockers=preparation_check.blockers,
            )

        datasets = self._confirmed_source_datasets(state)

        incomplete = tuple(
            dataset.confirmed_display_name
            for dataset in datasets
            if dataset.preparation_status not in self._PREPARATION_COMPLETE
        )

        if incomplete:
            return ReadinessResult(
                stage=WorkspaceStage.FIELD_MAPPING,
                ready=False,
                message="Confirm Data Preparation for every included dataset.",
                blockers=tuple(f"Preparation not confirmed: {name}" for name in incomplete),
            )

        return ReadinessResult(
            stage=WorkspaceStage.FIELD_MAPPING,
            ready=True,
            message="All included datasets are ready for Field Mapping.",
        )

    def _check_audit_procedures(
        self,
        state: WorkspaceState,
    ) -> ReadinessResult:
        mapping_check = self._check_field_mapping(state)

        if not mapping_check.ready:
            return ReadinessResult(
                stage=WorkspaceStage.AUDIT_PROCEDURES,
                ready=False,
                message=mapping_check.message,
                blockers=mapping_check.blockers,
            )

        datasets = self._confirmed_source_datasets(state)

        incomplete = tuple(
            dataset.confirmed_display_name
            for dataset in datasets
            if dataset.mapping_status not in self._MAPPING_COMPLETE
        )

        if incomplete:
            return ReadinessResult(
                stage=WorkspaceStage.AUDIT_PROCEDURES,
                ready=False,
                message="Confirm Field Mapping for every included dataset.",
                blockers=tuple(f"Field Mapping not confirmed: {name}" for name in incomplete),
            )

        return ReadinessResult(
            stage=WorkspaceStage.AUDIT_PROCEDURES,
            ready=True,
            message="The workspace is ready to select audit procedures.",
        )

    @staticmethod
    def _confirmed_source_datasets(
        state: WorkspaceState,
    ) -> tuple[WorksheetDataset, ...]:
        """Return selected datasets confirmed in Data Sources."""

        return tuple(
            dataset
            for dataset in state.selected_datasets
            if dataset.status == PreparationStatus.CONFIRMED
        )
