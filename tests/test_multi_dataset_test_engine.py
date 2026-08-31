"""Tests for generic multi-dataset Test Engine execution."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from auditor_support_tool.core.audit_execution_models import (
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecord,
    AuditRecordSource,
)
from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_dataset_resolution import (
    ProcedureDatasetBundle,
    ProcedureDatasetResolver,
    ProcedureDatasetSource,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineStatus as EngineStatus,
)
from auditor_support_tool.core.test_engine_service import (
    TestEngineService as EngineService,
)
from auditor_support_tool.core.workbook_package import DatasetType


class StubSource:
    """Minimal audit source with configurable mapping identity."""

    def __init__(
        self,
        *,
        dataset_id: str,
        fields: tuple[str, ...],
        mapping_fingerprint: str,
        record_count: int = 3,
    ) -> None:
        self._dataset_id = dataset_id
        self._fields = tuple(fields)
        self._mapping_fingerprint = mapping_fingerprint
        self._record_count = record_count

    @property
    def dataset_id(self) -> str:
        return self._dataset_id

    @property
    def record_count(self) -> int:
        return self._record_count

    @property
    def standard_fields(self) -> tuple[str, ...]:
        return self._fields

    @property
    def mapping_fingerprint(self) -> str:
        return self._mapping_fingerprint

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        return standard_field_key in self._fields

    def iter_records(self) -> Iterator[AuditRecord]:
        return iter(())


class StubMultiDatasetProcedure:
    """Dataset-aware procedure proving the generic execution contract."""

    def __init__(self) -> None:
        self._definition = ProcedureDefinition.create(
            procedure_id="PROC011",
            name="Multi Dataset Example",
            category="Example Audit Area",
            dataset_requirements=(
                ProcedureDatasetRequirement.create(
                    role="primary_data",
                    dataset_type=DatasetType.GENERAL_LEDGER,
                    required_fields=("account_code",),
                    primary=True,
                ),
                ProcedureDatasetRequirement.create(
                    role="reference_data",
                    dataset_type=DatasetType.CHART_OF_ACCOUNTS,
                    required_fields=("account_code",),
                ),
            ),
            procedure_version="1.0",
        )
        self.run_count = 0
        self.reference_dataset_id = ""

    @property
    def definition(self) -> ProcedureDefinition:
        return self._definition

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        del cancellation_token

        self.run_count += 1

        assert isinstance(source, ProcedureDatasetBundle)

        reference = source.require_source("reference_data")
        self.reference_dataset_id = reference.dataset_id

        return ProcedureResult.create(
            context=context,
            population_count=source.record_count,
            records_evaluated_count=source.record_count,
            metrics={
                "reference_population": reference.record_count,
            },
        )


def _descriptor(
    *,
    dataset_type: DatasetType,
    source: StubSource,
) -> ProcedureDatasetSource:
    return ProcedureDatasetSource.create(
        dataset_type=dataset_type,
        source=source,
    )


def _sources(
    *,
    reference_fields: tuple[str, ...] = ("account_code",),
    reference_mapping: str = "c" * 64,
) -> tuple[
    StubSource,
    StubSource,
    tuple[ProcedureDatasetSource, ...],
]:
    primary = StubSource(
        dataset_id="gl-dataset",
        fields=("account_code",),
        mapping_fingerprint="b" * 64,
        record_count=5,
    )
    reference = StubSource(
        dataset_id="coa-dataset",
        fields=reference_fields,
        mapping_fingerprint=reference_mapping,
        record_count=12,
    )

    descriptors = (
        _descriptor(
            dataset_type=DatasetType.GENERAL_LEDGER,
            source=primary,
        ),
        _descriptor(
            dataset_type=DatasetType.CHART_OF_ACCOUNTS,
            source=reference,
        ),
    )

    return primary, reference, descriptors


def _engine(
    procedure: StubMultiDatasetProcedure,
) -> EngineService:
    registry = ProcedureRegistry()
    registry.register(procedure)
    return EngineService(registry=registry)


def _source_file(tmp_path: Path) -> Path:
    source_path = tmp_path / "multi-dataset.xlsx"
    source_path.write_bytes(b"regression fixture")
    return source_path


def test_dataset_bundle_exposes_primary_and_reference_sources() -> None:
    primary, reference, descriptors = _sources()
    definition = StubMultiDatasetProcedure().definition

    resolution = ProcedureDatasetResolver().resolve(
        definition=definition,
        active_source=descriptors[0],
        available_sources=descriptors,
    )
    bundle = ProcedureDatasetBundle.create(resolution)

    assert bundle.dataset_id == primary.dataset_id
    assert bundle.record_count == primary.record_count
    assert bundle.standard_fields == primary.standard_fields
    assert bundle.roles == (
        "primary_data",
        "reference_data",
    )
    assert bundle.require_source("primary_data") is primary
    assert bundle.require_source("reference_data") is reference


def test_dataset_bundle_fingerprint_includes_reference_mapping() -> None:
    primary, _, first_descriptors = _sources(
        reference_mapping="c" * 64,
    )
    _, _, second_descriptors = _sources(
        reference_mapping="d" * 64,
    )
    definition = StubMultiDatasetProcedure().definition
    resolver = ProcedureDatasetResolver()

    first = ProcedureDatasetBundle.create(
        resolver.resolve(
            definition=definition,
            active_source=first_descriptors[0],
            available_sources=first_descriptors,
        )
    )
    second = ProcedureDatasetBundle.create(
        resolver.resolve(
            definition=definition,
            active_source=ProcedureDatasetSource.create(
                dataset_type=DatasetType.GENERAL_LEDGER,
                source=primary,
            ),
            available_sources=second_descriptors,
        )
    )

    assert len(first.mapping_fingerprint) == 64
    assert first.mapping_fingerprint != second.mapping_fingerprint


def test_engine_runs_dataset_aware_procedure_with_resolved_bundle(
    tmp_path: Path,
) -> None:
    procedure = StubMultiDatasetProcedure()
    primary, reference, descriptors = _sources()

    outcome = _engine(procedure).run(
        procedure_id="PROC011",
        source=primary,
        source_path=_source_file(tmp_path),
        dataset_sources=descriptors,
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.population_count == 5
    assert outcome.result.metrics["reference_population"] == 12
    assert procedure.reference_dataset_id == reference.dataset_id
    assert procedure.run_count == 1


def test_engine_context_fingerprints_all_dataset_mappings(
    tmp_path: Path,
) -> None:
    procedure = StubMultiDatasetProcedure()
    primary, _, descriptors = _sources()
    resolver = ProcedureDatasetResolver()

    expected_bundle = ProcedureDatasetBundle.create(
        resolver.resolve(
            definition=procedure.definition,
            active_source=descriptors[0],
            available_sources=descriptors,
        )
    )

    outcome = _engine(procedure).run(
        procedure_id="PROC011",
        source=primary,
        source_path=_source_file(tmp_path),
        dataset_sources=descriptors,
    )

    assert outcome.result is not None
    assert outcome.result.context.mapping_fingerprint == expected_bundle.mapping_fingerprint
    assert outcome.result.context.mapping_fingerprint != primary.mapping_fingerprint


def test_engine_blocks_dataset_aware_procedure_when_reference_is_missing(
    tmp_path: Path,
) -> None:
    procedure = StubMultiDatasetProcedure()
    primary, _, descriptors = _sources()

    outcome = _engine(procedure).run(
        procedure_id="PROC011",
        source=primary,
        source_path=_source_file(tmp_path),
        dataset_sources=(descriptors[0],),
    )

    assert outcome.status == EngineStatus.BLOCKED
    assert outcome.readiness is not None
    assert outcome.readiness.missing_required_datasets == ("reference_data",)
    assert procedure.run_count == 0


def test_engine_blocks_when_reference_required_field_is_unmapped(
    tmp_path: Path,
) -> None:
    procedure = StubMultiDatasetProcedure()
    primary, _, descriptors = _sources(
        reference_fields=(),
    )

    outcome = _engine(procedure).run(
        procedure_id="PROC011",
        source=primary,
        source_path=_source_file(tmp_path),
        dataset_sources=descriptors,
    )

    assert outcome.status == EngineStatus.BLOCKED
    assert outcome.readiness is not None
    assert outcome.readiness.missing_required_fields == ("reference_data.account_code",)
    assert procedure.run_count == 0


def test_dataset_aware_execution_requires_active_dataset_metadata(
    tmp_path: Path,
) -> None:
    procedure = StubMultiDatasetProcedure()
    primary, _, _ = _sources()

    outcome = _engine(procedure).run(
        procedure_id="PROC011",
        source=primary,
        source_path=_source_file(tmp_path),
    )

    assert outcome.status == EngineStatus.FAILED
    assert "dataset descriptor" in outcome.error_message.lower()
    assert procedure.run_count == 0
