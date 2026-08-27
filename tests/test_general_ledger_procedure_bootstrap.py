"""Tests for General Ledger procedure registration."""

from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_bootstrap import (
    create_general_ledger_procedure_registry,
    register_general_ledger_procedures,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    segregation_of_duties,
    weekend_transactions,
)


def test_gl003_is_registered_automatically() -> None:
    """The first executable GL procedure should be available automatically."""

    registry = create_general_ledger_procedure_registry()

    procedure = registry.require("GL003")

    assert isinstance(
        procedure,
        weekend_transactions.WeekendTransactionsProcedure,
    )


def test_display_identifier_resolves_registered_gl003() -> None:
    """Automatic registration should retain normal registry lookup behavior."""

    registry = create_general_ledger_procedure_registry()

    assert registry.get("GL-003") is registry.get("GL003")


def test_gl006_is_registered_automatically() -> None:
    """The implemented SoD procedure should be registered automatically."""

    registry = create_general_ledger_procedure_registry()

    procedure = registry.require("GL006")

    assert isinstance(
        procedure,
        segregation_of_duties.SegregationOfDutiesProcedure,
    )


def test_registration_can_populate_shared_application_registry() -> None:
    """The GL domain should register into a registry owned by the application."""

    registry = ProcedureRegistry()

    register_general_ledger_procedures(registry)

    assert registry.is_registered("GL001")
    assert registry.is_registered("GL003")
    assert registry.is_registered("GL006")


def test_bootstrap_registers_only_current_executable_procedures() -> None:
    """The registry should expose only procedures with actual implementations."""

    registry = create_general_ledger_procedure_registry()

    assert tuple(definition.procedure_id for definition in registry.definitions) == (
        "GL001",
        "GL003",
        "GL006",
    )
