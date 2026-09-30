"""Registration of executable payroll audit procedures."""

from auditor_support_tool.core.procedure_registry import ProcedureRegistry
from auditor_support_tool.domains.financial_audit.payroll.procedures.payroll_gl_employee_validation import (  # noqa: E501
    PayrollGlEmployeeValidationProcedure,
)


def register_payroll_procedures(registry: ProcedureRegistry) -> None:
    """Register all currently executable payroll procedures."""

    registry.register(PayrollGlEmployeeValidationProcedure())


def create_payroll_procedure_registry() -> ProcedureRegistry:
    """Return a registry populated with executable payroll procedures."""

    registry = ProcedureRegistry()
    register_payroll_procedures(registry)
    return registry
