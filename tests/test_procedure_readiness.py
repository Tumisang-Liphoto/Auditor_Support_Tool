"""Tests for generic audit-procedure readiness checks."""

from __future__ import annotations

from collections.abc import Iterator

from auditor_support_tool.core.audit_record_source import (
    AuditRecord,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadinessService,
    ProcedureReadinessStatus,
)


class StubRecordSource:
    """Minimal generic source used for readiness tests."""

    def __init__(
        self,
        *standard_fields: str,
    ) -> None:
        self._standard_fields = tuple(standard_fields)

    @property
    def dataset_id(self) -> str:
        """Return a generic dataset identifier."""

        return "dataset-123"

    @property
    def record_count(self) -> int:
        """Return an arbitrary population count."""

        return 100

    @property
    def standard_fields(self) -> tuple[str, ...]:
        """Return available standard fields."""

        return self._standard_fields

    @property
    def mapping_fingerprint(self) -> str:
        """Return a deterministic placeholder fingerprint."""

        return "a" * 64

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        """Return whether a standard field is available."""

        return standard_field_key in self._standard_fields

    def iter_records(self) -> Iterator[AuditRecord]:
        """Readiness checks must never iterate source records."""

        raise AssertionError("Readiness checking must not iterate records.")


def create_definition(
    *,
    procedure_id: str = "PROC001",
    required_fields: tuple[str, ...] = (),
    helpful_fields: tuple[str, ...] = (),
) -> ProcedureDefinition:
    """Create a generic procedure definition."""

    return ProcedureDefinition.create(
        procedure_id=procedure_id,
        name="Example Procedure",
        category="Example Audit Area",
        required_fields=required_fields,
        helpful_fields=helpful_fields,
    )


def test_procedure_is_ready_when_required_fields_exist() -> None:
    """Available required fields should allow execution."""

    definition = create_definition(
        required_fields=("primary_field",),
    )
    source = StubRecordSource(
        "primary_field",
    )

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.status == (ProcedureReadinessStatus.READY)
    assert readiness.can_run
    assert not readiness.needs_attention
    assert readiness.missing_required_fields == ()


def test_missing_required_field_blocks_execution() -> None:
    """A missing required field should block the procedure."""

    definition = create_definition(
        required_fields=(
            "primary_field",
            "secondary_field",
        ),
    )
    source = StubRecordSource(
        "primary_field",
    )

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.status == (ProcedureReadinessStatus.BLOCKED)
    assert not readiness.can_run
    assert readiness.needs_attention

    assert readiness.mapped_required_fields == ("primary_field",)
    assert readiness.missing_required_fields == ("secondary_field",)


def test_no_helpful_fields_produces_warning_when_defined() -> None:
    """Helpful fields may be absent without blocking execution."""

    definition = create_definition(
        required_fields=("primary_field",),
        helpful_fields=("supporting_field",),
    )
    source = StubRecordSource(
        "primary_field",
    )

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.status == (ProcedureReadinessStatus.READY_WITH_WARNING)
    assert readiness.can_run
    assert readiness.needs_attention
    assert len(readiness.warnings) == 1


def test_available_helpful_field_removes_warning() -> None:
    """At least one helpful field should support normal readiness."""

    definition = create_definition(
        required_fields=("primary_field",),
        helpful_fields=(
            "supporting_field",
            "additional_field",
        ),
    )
    source = StubRecordSource(
        "primary_field",
        "supporting_field",
    )

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.status == (ProcedureReadinessStatus.READY)
    assert readiness.warnings == ()

    assert readiness.mapped_helpful_fields == ("supporting_field",)
    assert readiness.missing_helpful_fields == ("additional_field",)


def test_procedure_without_field_requirements_is_ready() -> None:
    """A procedure with no declared field requirements may run."""

    definition = create_definition()
    source = StubRecordSource()

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.status == (ProcedureReadinessStatus.READY)
    assert readiness.can_run


def test_readiness_preserves_canonical_procedure_identity() -> None:
    """Readiness results should carry the canonical procedure ID."""

    definition = create_definition(
        procedure_id="PAY-001",
    )
    source = StubRecordSource()

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.procedure_id == "PAY001"


def test_readiness_reports_all_missing_helpful_fields() -> None:
    """The UI should know which optional mappings are unavailable."""

    definition = create_definition(
        helpful_fields=(
            "supporting_field",
            "additional_field",
        ),
    )
    source = StubRecordSource()

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.missing_helpful_fields == (
        "supporting_field",
        "additional_field",
    )


def test_readiness_does_not_iterate_population() -> None:
    """Readiness should remain instant regardless of population size."""

    definition = create_definition(
        required_fields=("primary_field",),
    )
    source = StubRecordSource(
        "primary_field",
    )

    readiness = ProcedureReadinessService().check(
        definition=definition,
        source=source,
    )

    assert readiness.can_run
