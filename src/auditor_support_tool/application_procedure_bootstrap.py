"""Application-level registration of executable audit procedures."""

from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_bootstrap import (
    register_general_ledger_procedures,
)


def create_application_procedure_registry() -> ProcedureRegistry:
    """Return the application's complete executable procedure registry."""

    registry = ProcedureRegistry()

    register_general_ledger_procedures(registry)

    return registry
