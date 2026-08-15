"""Tests for the generic executable procedure registry."""

from __future__ import annotations

import pytest

from auditor_support_tool.core.audit_execution_models import (
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_registry import (
    ProcedureNotRegisteredError,
    ProcedureRegistrationError,
    ProcedureRegistry,
)


class StubProcedure:
    """Generic executable procedure used only for registry tests."""

    def __init__(
        self,
        procedure_id: str,
    ) -> None:
        self._definition = ProcedureDefinition.create(
            procedure_id=procedure_id,
            name=f"Procedure {procedure_id}",
            category="Example Audit Area",
        )

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
        """Registry tests should never execute procedure logic."""

        raise AssertionError("ProcedureRegistry must not execute procedures.")


def test_procedure_can_be_registered() -> None:
    """An executable procedure should be registered by canonical ID."""

    registry = ProcedureRegistry()
    procedure = StubProcedure("PROC001")

    registry.register(procedure)

    assert registry.get("PROC001") is procedure


def test_display_identifier_resolves_registered_procedure() -> None:
    """Lookup should accept the user-facing display identifier."""

    registry = ProcedureRegistry()
    procedure = StubProcedure("PAY001")

    registry.register(procedure)

    assert registry.get("PAY-001") is procedure


def test_lookup_is_case_insensitive() -> None:
    """Procedure lookup should use canonical identity normalisation."""

    registry = ProcedureRegistry()
    procedure = StubProcedure("ITGC001")

    registry.register(procedure)

    assert registry.get("itgc-001") is procedure


def test_duplicate_registration_is_rejected() -> None:
    """Only one executable implementation may own a procedure ID."""

    registry = ProcedureRegistry()

    registry.register(StubProcedure("PROC001"))

    with pytest.raises(
        ProcedureRegistrationError,
        match="already registered",
    ):
        registry.register(StubProcedure("PROC001"))


def test_unknown_procedure_returns_none() -> None:
    """Optional lookup should not raise for an unregistered procedure."""

    registry = ProcedureRegistry()

    assert registry.get("PROC999") is None


def test_invalid_identifier_returns_none_from_optional_lookup() -> None:
    """Malformed identifiers should not resolve to unrelated procedures."""

    registry = ProcedureRegistry()

    assert registry.get("not-a-procedure") is None


def test_required_lookup_raises_when_not_registered() -> None:
    """Required lookup should clearly report unavailable implementations."""

    registry = ProcedureRegistry()

    with pytest.raises(
        ProcedureNotRegisteredError,
        match="PROC001",
    ):
        registry.require("PROC001")


def test_registry_reports_registration_status() -> None:
    """The UI should be able to determine implementation availability."""

    registry = ProcedureRegistry()
    registry.register(StubProcedure("PROC001"))

    assert registry.is_registered("PROC001")
    assert registry.is_registered("PROC-001")
    assert not registry.is_registered("PROC002")


def test_registry_exposes_registered_definitions() -> None:
    """The UI should be able to obtain definitions without executing tests."""

    registry = ProcedureRegistry()

    first = StubProcedure("PROC001")
    second = StubProcedure("PROC002")

    registry.register(first)
    registry.register(second)

    assert registry.definitions == (
        first.definition,
        second.definition,
    )


def test_registry_preserves_registration_order() -> None:
    """Registration order should remain stable for deterministic consumers."""

    registry = ProcedureRegistry()

    first = StubProcedure("PROC001")
    second = StubProcedure("PAY001")
    third = StubProcedure("ITGC001")

    registry.register_many(
        (
            first,
            second,
            third,
        )
    )

    assert registry.procedures == (
        first,
        second,
        third,
    )


def test_registration_requires_procedure_definition() -> None:
    """Malformed implementations should fail during registration."""

    class InvalidProcedure:
        definition = "not-a-definition"

        def run(self) -> None:
            pass

    registry = ProcedureRegistry()

    with pytest.raises(
        ProcedureRegistrationError,
        match="ProcedureDefinition",
    ):
        registry.register(InvalidProcedure())  # type: ignore[arg-type]


def test_registration_requires_callable_runner() -> None:
    """Definitions alone are not executable implementations."""

    class InvalidProcedure:
        definition = ProcedureDefinition.create(
            procedure_id="PROC001",
            name="Example Procedure",
            category="Example Audit Area",
        )
        run = None

    registry = ProcedureRegistry()

    with pytest.raises(
        ProcedureRegistrationError,
        match="callable",
    ):
        registry.register(InvalidProcedure())  # type: ignore[arg-type]
