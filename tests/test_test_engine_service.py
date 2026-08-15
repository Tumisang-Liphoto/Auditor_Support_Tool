"""Tests for central generic Test Engine orchestration."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

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


class StubRecordSource:
    """Generic source used for Test Engine tests."""

    def __init__(
        self,
        *,
        standard_fields: tuple[str, ...] = (),
        record_count: int = 3,
    ) -> None:
        self._standard_fields = standard_fields
        self._record_count = record_count

    @property
    def dataset_id(self) -> str:
        """Return the test dataset identifier."""

        return "dataset-123"

    @property
    def record_count(self) -> int:
        """Return the configured population count."""

        return self._record_count

    @property
    def standard_fields(self) -> tuple[str, ...]:
        """Return available standard audit fields."""

        return self._standard_fields

    @property
    def mapping_fingerprint(self) -> str:
        """Return a deterministic placeholder mapping fingerprint."""

        return "b" * 64

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        """Return whether a standard audit field is available."""

        return standard_field_key in self._standard_fields

    def iter_records(self) -> Iterator[AuditRecord]:
        """Return an empty iterator for orchestration-only tests."""

        return iter(())


class StubProcedure:
    """Generic executable procedure used for engine tests."""

    def __init__(
        self,
        *,
        required_fields: tuple[str, ...] = (),
        helpful_fields: tuple[str, ...] = (),
        behavior: str = "complete",
    ) -> None:
        self._definition = ProcedureDefinition.create(
            procedure_id="PROC001",
            name="Example Procedure",
            category="Example Audit Area",
            required_fields=required_fields,
            helpful_fields=helpful_fields,
            procedure_version="2.0",
        )
        self.behavior = behavior
        self.run_count = 0

    @property
    def definition(self) -> ProcedureDefinition:
        """Return the generic procedure definition."""

        return self._definition

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        """Execute the configured stub behavior."""

        self.run_count += 1

        if self.behavior == "raise":
            raise RuntimeError("Procedure logic failed.")

        if self.behavior == "wrong_population":
            return ProcedureResult.create(
                context=context,
                population_count=(source.record_count + 1),
                records_evaluated_count=(source.record_count + 1),
            )

        return ProcedureResult.create(
            context=context,
            population_count=source.record_count,
            records_evaluated_count=source.record_count,
        )


def create_source_file(
    tmp_path: Path,
) -> Path:
    """Create a source file for integrity hashing."""

    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "reference,amount\nA001,100\n",
        encoding="utf-8",
    )

    return source_path


def create_engine(
    procedure: StubProcedure | None = None,
) -> EngineService:
    """Create a Test Engine with an optional registered procedure."""

    registry = ProcedureRegistry()

    if procedure is not None:
        registry.register(procedure)

    return EngineService(registry=registry)


def test_registered_ready_procedure_runs_to_completion(
    tmp_path: Path,
) -> None:
    """A ready registered procedure should complete through one engine call."""

    procedure = StubProcedure(
        required_fields=("primary_field",),
    )
    engine = create_engine(procedure)
    source = StubRecordSource(
        standard_fields=("primary_field",),
    )

    outcome = engine.run(
        procedure_id="PROC-001",
        source=source,
        source_path=create_source_file(tmp_path),
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.completed
    assert outcome.was_executed
    assert outcome.has_result

    assert outcome.result is not None
    assert outcome.result.population_count == 3

    assert procedure.run_count == 1


def test_unregistered_procedure_returns_not_implemented() -> None:
    """Known-format IDs without implementations should not execute."""

    engine = create_engine()
    source = StubRecordSource()

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=Path("source-file-need-not-exist.csv"),
    )

    assert outcome.status == (EngineStatus.NOT_IMPLEMENTED)
    assert not outcome.was_executed
    assert not outcome.has_result


def test_missing_required_field_blocks_before_execution() -> None:
    """Readiness should stop execution before source hashing or procedure work."""

    procedure = StubProcedure(
        required_fields=("required_field",),
    )
    engine = create_engine(procedure)
    source = StubRecordSource()

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=Path("source-file-need-not-exist.csv"),
    )

    assert outcome.status == EngineStatus.BLOCKED
    assert not outcome.was_executed
    assert procedure.run_count == 0

    assert outcome.readiness is not None
    assert outcome.readiness.missing_required_fields == ("required_field",)


def test_helpful_field_warning_does_not_require_extra_confirmation(
    tmp_path: Path,
) -> None:
    """A warning should not add another click when required fields are ready."""

    procedure = StubProcedure(
        required_fields=("primary_field",),
        helpful_fields=("supporting_field",),
    )
    engine = create_engine(procedure)
    source = StubRecordSource(
        standard_fields=("primary_field",),
    )

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=create_source_file(tmp_path),
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.readiness is not None
    assert outcome.readiness.can_run
    assert outcome.readiness.needs_attention
    assert procedure.run_count == 1


def test_engine_carries_audit_period_and_parameters(
    tmp_path: Path,
) -> None:
    """Workspace scope and parameters should reach the procedure automatically."""

    procedure = StubProcedure()
    engine = create_engine(procedure)
    source = StubRecordSource()

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=create_source_file(tmp_path),
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
        parameters={
            "threshold": 1000,
        },
    )

    assert outcome.result is not None

    context = outcome.result.context

    assert context.audit_period_start == "2026-04-01"
    assert context.audit_period_end == "2027-03-31"
    assert context.parameters == {
        "threshold": 1000,
    }
    assert context.procedure_version == "2.0"


def test_pre_cancelled_request_returns_cancelled(
    tmp_path: Path,
) -> None:
    """Cancellation should pass through the engine without procedure work."""

    procedure = StubProcedure()
    engine = create_engine(procedure)
    source = StubRecordSource()

    token = ExecutionCancellationToken()
    token.cancel()

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=create_source_file(tmp_path),
        cancellation_token=token,
    )

    assert outcome.status == EngineStatus.CANCELLED
    assert outcome.was_executed
    assert not outcome.has_result
    assert procedure.run_count == 0


def test_procedure_exception_returns_failed_outcome(
    tmp_path: Path,
) -> None:
    """Procedure failures should be returned as controlled engine outcomes."""

    procedure = StubProcedure(behavior="raise")
    engine = create_engine(procedure)
    source = StubRecordSource()

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=create_source_file(tmp_path),
    )

    assert outcome.status == EngineStatus.FAILED
    assert outcome.was_executed
    assert not outcome.has_result
    assert outcome.error_message == ("Procedure logic failed.")


def test_invalid_result_population_becomes_failed_execution(
    tmp_path: Path,
) -> None:
    """Results must reconcile to the actual source population."""

    procedure = StubProcedure(behavior="wrong_population")
    engine = create_engine(procedure)
    source = StubRecordSource(record_count=3)

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=create_source_file(tmp_path),
    )

    assert outcome.status == EngineStatus.FAILED
    assert outcome.was_executed
    assert not outcome.has_result

    assert "population count" in (outcome.error_message)


def test_invalid_audit_period_returns_failed_without_procedure_execution(
    tmp_path: Path,
) -> None:
    """Invalid workspace scope should fail before procedure logic begins."""

    procedure = StubProcedure()
    engine = create_engine(procedure)
    source = StubRecordSource()

    outcome = engine.run(
        procedure_id="PROC001",
        source=source,
        source_path=create_source_file(tmp_path),
        audit_period_start="2027-03-31",
        audit_period_end="2026-04-01",
    )

    assert outcome.status == EngineStatus.FAILED
    assert not outcome.was_executed
    assert procedure.run_count == 0

    assert "end cannot be before" in (outcome.error_message)


def test_malformed_procedure_identifier_is_rejected() -> None:
    """Malformed IDs are caller errors rather than implementation states."""

    engine = create_engine()
    source = StubRecordSource()

    with pytest.raises(
        ValueError,
        match="Procedure identifier",
    ):
        engine.run(
            procedure_id="not-a-procedure",
            source=source,
            source_path=Path("unused.csv"),
        )
