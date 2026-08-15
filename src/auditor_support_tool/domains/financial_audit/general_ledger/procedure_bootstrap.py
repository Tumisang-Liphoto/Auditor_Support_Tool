"""Registration of executable General Ledger audit procedures."""

from __future__ import annotations

from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    weekend_transactions,
)


def register_general_ledger_procedures(
    registry: ProcedureRegistry,
) -> None:
    """Register all currently executable General Ledger procedures."""

    registry.register(weekend_transactions.WeekendTransactionsProcedure())


def create_general_ledger_procedure_registry() -> ProcedureRegistry:
    """Return a registry populated with executable GL procedures."""

    registry = ProcedureRegistry()

    register_general_ledger_procedures(registry)

    return registry
