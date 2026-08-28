"""Tests for multi-dataset resolution, readiness and availability."""

from __future__ import annotations

from dataclasses import dataclass

from auditor_support_tool.core.procedure_availability import (
    ProcedureAvailabilityService,
)
from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_dataset_resolution import (
    ProcedureDatasetResolver,
    ProcedureDatasetSource,
)
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadinessService,
    ProcedureReadinessStatus,
)
from auditor_support_tool.core.workbook_package import DatasetType


class StubSource:
    """Minimal structural audit-record source for readiness tests."""

    def __init__(
        self,
        dataset_id: str,
        fields: tuple[str, ...],
    ) -> None:
        self.dataset_id = dataset_id
        self.record_count = 0
        self.standard_fields = tuple(sorted(fields))
        self.mapping_fingerprint = "a" * 64
        self._fields = set(fields)

    def has_field(self, standard_field_key: str) -> bool:
        return standard_field_key in self._fields

    def iter_records(self):
        return iter(())


@dataclass(frozen=True)
class StubProcedure:
    """Minimal implemented procedure used by availability tests."""

    definition: ProcedureDefinition


def _source(
    dataset_id: str,
    dataset_type: DatasetType,
    fields: tuple[str, ...] = ("account_code",),
) -> ProcedureDatasetSource:
    return ProcedureDatasetSource.create(
        dataset_type=dataset_type,
        source=StubSource(dataset_id, fields),
    )


def _gl011_definition() -> ProcedureDefinition:
    return ProcedureDefinition.create(
        procedure_id="GL011",
        name="Unmapped Accounts",
        category="General Ledger",
        dataset_requirements=(
            ProcedureDatasetRequirement.create(
                role="general_ledger",
                dataset_type=DatasetType.GENERAL_LEDGER,
                required_fields=("account_code",),
                primary=True,
            ),
            ProcedureDatasetRequirement.create(
                role="chart_of_accounts",
                dataset_type=DatasetType.CHART_OF_ACCOUNTS,
                required_fields=("account_code",),
            ),
        ),
    )


def test_resolver_matches_primary_and_reference_datasets() -> None:
    resolver = ProcedureDatasetResolver()
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)
    chart = _source("coa", DatasetType.CHART_OF_ACCOUNTS)

    resolution = resolver.resolve(
        definition=_gl011_definition(),
        active_source=general_ledger,
        available_sources=(general_ledger, chart),
    )

    assert resolution.complete is True
    assert resolution.unresolved_roles == ()
    assert resolution.primary is not None
    assert resolution.primary.source == general_ledger
    assert resolution.source_for_role("chart_of_accounts").dataset_id == "coa"


def test_resolver_does_not_guess_missing_reference_dataset() -> None:
    resolver = ProcedureDatasetResolver()
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)

    resolution = resolver.resolve(
        definition=_gl011_definition(),
        active_source=general_ledger,
        available_sources=(general_ledger,),
    )

    assert resolution.complete is False
    assert resolution.unresolved_roles == ("chart_of_accounts",)


def test_resolver_blocks_ambiguous_reference_dataset() -> None:
    resolver = ProcedureDatasetResolver()
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)
    chart_one = _source("coa-1", DatasetType.CHART_OF_ACCOUNTS)
    chart_two = _source("coa-2", DatasetType.CHART_OF_ACCOUNTS)

    resolution = resolver.resolve(
        definition=_gl011_definition(),
        active_source=general_ledger,
        available_sources=(
            general_ledger,
            chart_one,
            chart_two,
        ),
    )

    assert resolution.complete is False
    assert resolution.unresolved_roles == ("chart_of_accounts",)
    assert "ambiguous" in resolution.datasets[1].reason


def test_primary_requirement_must_match_active_dataset() -> None:
    resolver = ProcedureDatasetResolver()
    chart = _source("coa", DatasetType.CHART_OF_ACCOUNTS)
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)

    resolution = resolver.resolve(
        definition=_gl011_definition(),
        active_source=chart,
        available_sources=(chart, general_ledger),
    )

    assert resolution.complete is False
    assert "general_ledger" in resolution.unresolved_roles


def test_multi_dataset_readiness_blocks_missing_reference() -> None:
    definition = _gl011_definition()
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)

    resolution = ProcedureDatasetResolver().resolve(
        definition=definition,
        active_source=general_ledger,
        available_sources=(general_ledger,),
    )

    readiness = ProcedureReadinessService().check_datasets(
        definition=definition,
        resolution=resolution,
    )

    assert readiness.status == ProcedureReadinessStatus.BLOCKED
    assert readiness.can_run is False
    assert readiness.missing_required_datasets == ("chart_of_accounts",)


def test_multi_dataset_readiness_blocks_missing_reference_field() -> None:
    definition = _gl011_definition()
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)
    chart = _source(
        "coa",
        DatasetType.CHART_OF_ACCOUNTS,
        fields=(),
    )

    resolution = ProcedureDatasetResolver().resolve(
        definition=definition,
        active_source=general_ledger,
        available_sources=(general_ledger, chart),
    )
    readiness = ProcedureReadinessService().check_datasets(
        definition=definition,
        resolution=resolution,
    )

    assert readiness.status == ProcedureReadinessStatus.BLOCKED
    assert readiness.missing_required_datasets == ()
    assert readiness.missing_required_fields == ("chart_of_accounts.account_code",)


def test_multi_dataset_readiness_is_ready_when_every_requirement_is_met() -> None:
    definition = _gl011_definition()
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)
    chart = _source("coa", DatasetType.CHART_OF_ACCOUNTS)

    resolution = ProcedureDatasetResolver().resolve(
        definition=definition,
        active_source=general_ledger,
        available_sources=(general_ledger, chart),
    )
    readiness = ProcedureReadinessService().check_datasets(
        definition=definition,
        resolution=resolution,
    )

    assert readiness.status == ProcedureReadinessStatus.READY
    assert readiness.can_run is True
    assert readiness.mapped_required_fields == (
        "general_ledger.account_code",
        "chart_of_accounts.account_code",
    )


def test_workspace_availability_hides_dataset_aware_procedure_until_ready() -> None:
    procedure = StubProcedure(_gl011_definition())
    general_ledger = _source("gl", DatasetType.GENERAL_LEDGER)
    chart = _source("coa", DatasetType.CHART_OF_ACCOUNTS)
    service = ProcedureAvailabilityService()

    unavailable = service.available_for_workspace(
        procedures=(procedure,),
        active_source=general_ledger,
        mapped_sources=(general_ledger,),
    )
    available = service.available_for_workspace(
        procedures=(procedure,),
        active_source=general_ledger,
        mapped_sources=(general_ledger, chart),
    )

    assert unavailable == ()
    assert len(available) == 1
    assert available[0].dataset_resolution is not None
    assert available[0].dataset_resolution.complete is True


def test_workspace_availability_preserves_legacy_single_dataset_procedures() -> None:
    definition = ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        required_fields=("transaction_date",),
    )
    procedure = StubProcedure(definition)
    active = _source(
        "gl",
        DatasetType.GENERAL_LEDGER,
        fields=("transaction_date",),
    )

    available = ProcedureAvailabilityService().available_for_workspace(
        procedures=(procedure,),
        active_source=active,
        mapped_sources=(active,),
    )

    assert len(available) == 1
    assert available[0].dataset_resolution is None
    assert available[0].readiness.can_run is True
