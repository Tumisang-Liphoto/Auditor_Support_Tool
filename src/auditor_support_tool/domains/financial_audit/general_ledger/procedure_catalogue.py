"""Canonical General Ledger procedure catalogue.

The catalogue follows the application-aligned, readiness-prioritised engine
design workbook. Internal IDs use the compact ``GL003`` form. User interfaces
may display the corresponding ``GL-003`` form.
"""

from __future__ import annotations

from dataclasses import dataclass

from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
    procedure_display_id,
)


@dataclass(frozen=True, slots=True)
class GeneralLedgerProcedureDefinition:
    """Identity and definition-readiness metadata for one GL procedure."""

    procedure_id: str
    name: str
    readiness_rank: int
    readiness_score: int
    readiness_band: str

    @property
    def display_id(self) -> str:
        """Return a UI-friendly identifier such as ``GL-003``."""

        return procedure_display_id(self.procedure_id)


GENERAL_LEDGER_PROCEDURES: tuple[GeneralLedgerProcedureDefinition, ...] = (
    GeneralLedgerProcedureDefinition(
        "GL003", "Weekend Transactions", 1, 90, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL006", "Segregation of Duties", 2, 89, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL011", "Unmapped Accounts", 3, 88, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL024", "Trial Balance Balance Check", 4, 87, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL028", "Multiple Employees Sharing Bank Account", 5, 86, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL032", "Text-Based Payroll Analysis", 6, 85, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL033", "Duplicate Narration Analysis", 7, 84, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL005", "Round Amount Transactions", 8, 83, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL014", "Public Holiday Transactions", 9, 82, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL022", "Unused Accounts", 10, 81, "Priority 1 - Nearly Ready"
    ),
    GeneralLedgerProcedureDefinition(
        "GL004", "High Value Transactions", 11, 76, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL007", "Manual Journal Analysis", 12, 75, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL008", "Period-End Transactions", 13, 74, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL010", "Payments to Unknown Employees", 14, 73, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL013", "Duplicate Journal Detection", 15, 72, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL017", "Duplicate Vendor Payments", 16, 71, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL021", "Account Usage Analysis", 17, 70, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL023", "Material Account Identification", 18, 69, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL001", "Duplicate Invoice Detection", 19, 68, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL002", "Duplicate Salary Payments", 20, 67, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL012", "GL-to-Trial Balance Reconciliation", 21, 66, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL015", "User Activity Analysis", 22, 65, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL016", "Weekend User Activity", 23, 64, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL018", "New Vendor Analysis", 24, 63, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL027", "Salary Above Approved Salary", 25, 62, "Priority 2 - Moderate Definition"
    ),
    GeneralLedgerProcedureDefinition(
        "GL009", "Vendor Concentration Analysis", 26, 49, "Priority 3 - Significant Definition Work"
    ),
    GeneralLedgerProcedureDefinition(
        "GL019", "Split Purchases", 27, 47, "Priority 3 - Significant Definition Work"
    ),
    GeneralLedgerProcedureDefinition(
        "GL020",
        "Dormant Period Followed by Activity Spike",
        28,
        45,
        "Priority 3 - Significant Definition Work",
    ),
    GeneralLedgerProcedureDefinition(
        "GL025", "Negative Balance Review", 29, 43, "Priority 3 - Significant Definition Work"
    ),
    GeneralLedgerProcedureDefinition(
        "GL026",
        "Unexpected Account Combinations",
        30,
        41,
        "Priority 3 - Significant Definition Work",
    ),
    GeneralLedgerProcedureDefinition(
        "GL029", "Payroll Misclassification", 31, 39, "Priority 3 - Significant Definition Work"
    ),
    GeneralLedgerProcedureDefinition(
        "GL030", "Benford's Law Analysis", 32, 35, "Priority 3 - Significant Definition Work"
    ),
    GeneralLedgerProcedureDefinition(
        "GL031", "Outlier Detection", 33, 33, "Priority 3 - Significant Definition Work"
    ),
)

_PROCEDURES_BY_ID = {
    definition.procedure_id: definition for definition in GENERAL_LEDGER_PROCEDURES
}


def get_general_ledger_procedure(
    procedure_id: str,
) -> GeneralLedgerProcedureDefinition | None:
    """Return a GL procedure definition by canonical/display identifier."""

    try:
        canonical = canonical_procedure_id(procedure_id)
    except ValueError:
        return None

    return _PROCEDURES_BY_ID.get(canonical)


def require_general_ledger_procedure(
    procedure_id: str,
) -> GeneralLedgerProcedureDefinition:
    """Return a GL procedure definition or raise a clear lookup error."""

    canonical = canonical_procedure_id(procedure_id)
    definition = _PROCEDURES_BY_ID.get(canonical)

    if definition is None:
        raise KeyError(f"Unknown General Ledger engine procedure ID: {canonical}")

    return definition
