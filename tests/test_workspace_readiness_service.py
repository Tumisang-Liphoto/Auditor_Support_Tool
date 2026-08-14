"""Tests for central audit-workspace readiness rules."""

from pathlib import Path

from openpyxl import Workbook

from auditor_support_tool.core.workbook_package import (
    FieldMappingStatus,
    PreparationStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_readiness_service import (
    WorkspaceReadinessService,
    WorkspaceStage,
)
from auditor_support_tool.core.workspace_state import WorkspaceState


def create_state() -> WorkspaceState:
    """Create an active empty workspace state."""

    state = WorkspaceState()
    state.start_workspace(
        WorkspaceIdentity.create(
            name="Readiness Test",
            auditee_name="Example Auditee",
            audit_year="2026",
        )
    )
    return state


def load_dataset(
    state: WorkspaceState,
    tmp_path: Path,
) -> WorksheetDataset:
    """Load one real workbook dataset into the workspace state."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"
    worksheet.append(
        [
            "Transaction Date",
            "Account Code",
            "Amount",
        ]
    )
    worksheet.append(
        [
            "2026-01-01",
            "1000",
            125.00,
        ]
    )

    path = tmp_path / "readiness.xlsx"
    workbook.save(path)

    package = WorkbookPackageService().build_package(path)
    state.set_workbook_package(package)

    dataset = package.get_dataset_by_worksheet("General_Ledger")
    assert dataset is not None

    return dataset


def test_data_sources_requires_workspace() -> None:
    """Data Sources should not be available without an active workspace."""

    state = WorkspaceState()
    service = WorkspaceReadinessService()

    result = service.check(
        state,
        WorkspaceStage.DATA_SOURCES,
    )

    assert not result.ready
    assert result.blockers


def test_data_sources_is_ready_for_active_workspace() -> None:
    """A created workspace may proceed to Data Sources."""

    state = create_state()
    service = WorkspaceReadinessService()

    assert service.can_access(
        state,
        WorkspaceStage.DATA_SOURCES,
    )


def test_data_profile_requires_confirmed_dataset(
    tmp_path: Path,
) -> None:
    """Data Profile requires at least one confirmed source dataset."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.NOT_REVIEWED

    result = service.check(
        state,
        WorkspaceStage.DATA_PROFILE,
    )

    assert not result.ready
    assert any("confirmed" in blocker.lower() for blocker in result.blockers)


def test_data_profile_is_ready_after_source_confirmation(
    tmp_path: Path,
) -> None:
    """A confirmed dataset may be reviewed in Data Profile."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED

    assert service.can_access(
        state,
        WorkspaceStage.DATA_PROFILE,
    )


def test_data_preparation_requires_profiles(
    tmp_path: Path,
) -> None:
    """Data Preparation requires profiles for all confirmed datasets."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED
    dataset.data_profile = None

    result = service.check(
        state,
        WorkspaceStage.DATA_PREPARATION,
    )

    assert not result.ready
    assert any("Missing data profile" in blocker for blocker in result.blockers)


def test_field_mapping_requires_confirmed_preparation(
    tmp_path: Path,
) -> None:
    """Field Mapping requires every included dataset to finish preparation."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.NOT_REVIEWED

    result = service.check(
        state,
        WorkspaceStage.FIELD_MAPPING,
    )

    assert not result.ready
    assert any("Preparation not confirmed" in blocker for blocker in result.blockers)


def test_field_mapping_accepts_preparation_with_warnings(
    tmp_path: Path,
) -> None:
    """Confirmed preparation warnings should not block Field Mapping."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.CONFIRMED_WITH_WARNINGS

    assert service.can_access(
        state,
        WorkspaceStage.FIELD_MAPPING,
    )


def test_audit_procedures_require_confirmed_mapping(
    tmp_path: Path,
) -> None:
    """Audit Procedures require mapping completion for every included dataset."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.CONFIRMED
    dataset.mapping_status = FieldMappingStatus.IN_PROGRESS

    result = service.check(
        state,
        WorkspaceStage.AUDIT_PROCEDURES,
    )

    assert not result.ready
    assert any("Field Mapping not confirmed" in blocker for blocker in result.blockers)


def test_audit_procedures_accept_not_applicable_mapping(
    tmp_path: Path,
) -> None:
    """Datasets without a mapping catalogue should not block the workflow."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.CONFIRMED
    dataset.mapping_status = FieldMappingStatus.NOT_APPLICABLE

    assert service.can_access(
        state,
        WorkspaceStage.AUDIT_PROCEDURES,
    )


def test_audit_procedures_ready_when_mapping_is_confirmed(
    tmp_path: Path,
) -> None:
    """A fully prepared and mapped workspace should reach Audit Procedures."""

    state = create_state()
    dataset = load_dataset(state, tmp_path)
    service = WorkspaceReadinessService()

    dataset.status = PreparationStatus.CONFIRMED
    dataset.preparation_status = PreparationStatus.CONFIRMED
    dataset.mapping_status = FieldMappingStatus.CONFIRMED

    result = service.check(
        state,
        WorkspaceStage.AUDIT_PROCEDURES,
    )

    assert result.ready
    assert not result.blockers
