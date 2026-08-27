"""Canonical General Ledger procedure catalogue.

Each catalogue entry contains one authoritative generic ProcedureDefinition
plus General Ledger implementation-readiness metadata.

Internal procedure IDs use compact identifiers such as ``GL003``. User
interfaces may display the corresponding ``GL-003`` form.
"""

from __future__ import annotations

from dataclasses import dataclass

from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
    ProcedureParameterType,
)


@dataclass(frozen=True, slots=True)
class GeneralLedgerProcedureCatalogueEntry:
    """One General Ledger procedure and its planning metadata."""

    definition: ProcedureDefinition
    readiness_rank: int
    readiness_score: int
    readiness_band: str

    @property
    def procedure_id(self) -> str:
        """Return the canonical procedure identifier."""

        return self.definition.procedure_id

    @property
    def display_id(self) -> str:
        """Return the UI-friendly procedure identifier."""

        return self.definition.display_id

    @property
    def name(self) -> str:
        """Return the procedure name."""

        return self.definition.name

    @property
    def category(self) -> str:
        """Return the procedure category."""

        return self.definition.category

    @property
    def description(self) -> str:
        """Return the procedure description."""

        return self.definition.description

    @property
    def required_fields(self) -> tuple[str, ...]:
        """Return standard fields required for execution."""

        return self.definition.required_fields

    @property
    def helpful_fields(self) -> tuple[str, ...]:
        """Return optional supporting standard fields."""

        return self.definition.helpful_fields

    @property
    def parameter_definitions(
        self,
    ) -> tuple[ProcedureParameterDefinition, ...]:
        """Return configurable procedure parameters."""

        return self.definition.parameter_definitions

    @property
    def procedure_version(self) -> str:
        """Return the procedure logic version."""

        return self.definition.procedure_version


# Compatibility name retained while catalogue consumers migrate to the more
# explicit catalogue-entry terminology.
GeneralLedgerProcedureDefinition = GeneralLedgerProcedureCatalogueEntry


def _entry(
    procedure_id: str,
    name: str,
    readiness_rank: int,
    readiness_score: int,
    readiness_band: str,
    *,
    description: str = "",
    required_fields: tuple[str, ...] = (),
    helpful_fields: tuple[str, ...] = (),
    parameter_definitions: tuple[ProcedureParameterDefinition, ...] = (),
    procedure_version: str = "1.0",
) -> GeneralLedgerProcedureCatalogueEntry:
    """Create one validated General Ledger catalogue entry."""

    return GeneralLedgerProcedureCatalogueEntry(
        definition=ProcedureDefinition.create(
            procedure_id=procedure_id,
            name=name,
            category="General Ledger",
            description=description,
            required_fields=required_fields,
            helpful_fields=helpful_fields,
            parameter_definitions=parameter_definitions,
            procedure_version=procedure_version,
        ),
        readiness_rank=readiness_rank,
        readiness_score=readiness_score,
        readiness_band=readiness_band,
    )


_GL003_PARAMETERS = (
    ProcedureParameterDefinition.create(
        key="weekend_days",
        label="Weekend days",
        value_type=ProcedureParameterType.MULTI_CHOICE,
        description=(
            "Select the days treated as weekend activity. Saturday and "
            "Sunday are selected by default."
        ),
        required=True,
        default_value=("Saturday", "Sunday"),
        choices=("Saturday", "Sunday"),
    ),
    ProcedureParameterDefinition.create(
        key="high_value_threshold",
        label="High-value threshold",
        value_type=ProcedureParameterType.DECIMAL,
        description=(
            "Optional monetary threshold used to identify high-value weekend transactions."
        ),
        placeholder="Example: 100000",
    ),
    ProcedureParameterDefinition.create(
        key="manual_journal_values",
        label="Manual-journal values",
        value_type=ProcedureParameterType.TEXT_LIST,
        description=(
            "Optional journal type or source values that identify manual "
            "journals. Separate multiple values with commas."
        ),
        placeholder="Example: Manual, Adjustment",
    ),
)


GENERAL_LEDGER_PROCEDURES: tuple[
    GeneralLedgerProcedureCatalogueEntry,
    ...,
] = (
    _entry(
        "GL003",
        "Weekend Transactions",
        1,
        90,
        "Priority 1 - Nearly Ready",
        description=(
            "Identifies transactions dated on Saturdays or Sundays for further audit scrutiny."
        ),
        required_fields=("transaction_date",),
        helpful_fields=(
            "journal_number",
            "account_code",
            "transaction_description",
            "debit_amount",
            "credit_amount",
            "transaction_amount",
            "vendor_code",
            "vendor_name",
            "entry_user",
            "approval_user",
            "journal_source",
            "journal_type",
        ),
        parameter_definitions=_GL003_PARAMETERS,
        procedure_version="1.0",
    ),
    _entry(
        "GL006",
        "Segregation of Duties",
        2,
        89,
        "Priority 1 - Nearly Ready",
        description=(
            "Identifies transactions entered and approved by the same "
            "user for further audit scrutiny."
        ),
        required_fields=(
            "entry_user",
            "approval_user",
        ),
        helpful_fields=(
            "posting_user",
            "transaction_id",
            "journal_number",
            "transaction_date",
            "posting_date",
            "transaction_amount",
            "account_code",
            "transaction_description",
            "approval_date",
            "approval_timestamp",
        ),
        procedure_version="1.0",
    ),
    _entry(
        "GL011",
        "Unmapped Accounts",
        3,
        88,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL024",
        "Trial Balance Balance Check",
        4,
        87,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL028",
        "Multiple Employees Sharing Bank Account",
        5,
        86,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL032",
        "Text-Based Payroll Analysis",
        6,
        85,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL033",
        "Duplicate Narration Analysis",
        7,
        84,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL005",
        "Round Amount Transactions",
        8,
        83,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL014",
        "Public Holiday Transactions",
        9,
        82,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL022",
        "Unused Accounts",
        10,
        81,
        "Priority 1 - Nearly Ready",
    ),
    _entry(
        "GL004",
        "High Value Transactions",
        11,
        76,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL007",
        "Manual Journal Analysis",
        12,
        75,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL008",
        "Period-End Transactions",
        13,
        74,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL010",
        "Payments to Unknown Employees",
        14,
        73,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL013",
        "Duplicate Journal Detection",
        15,
        72,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL017",
        "Duplicate Vendor Payments",
        16,
        71,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL021",
        "Account Usage Analysis",
        17,
        70,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL023",
        "Material Account Identification",
        18,
        69,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL001",
        "Duplicate Invoice Detection",
        19,
        68,
        "Priority 2 - Moderate Definition",
        description=(
            "Identifies repeated invoice numbers that may require further audit scrutiny."
        ),
        required_fields=("invoice_number",),
        helpful_fields=(
            "vendor_code",
            "vendor_name",
            "transaction_date",
            "journal_number",
            "transaction_amount",
            "debit_amount",
            "credit_amount",
            "transaction_description",
            "account_code",
            "entry_user",
            "approval_user",
            "journal_source",
        ),
        procedure_version="1.0",
    ),
    _entry(
        "GL002",
        "Duplicate Salary Payments",
        20,
        67,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL012",
        "GL-to-Trial Balance Reconciliation",
        21,
        66,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL015",
        "User Activity Analysis",
        22,
        65,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL016",
        "Weekend User Activity",
        23,
        64,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL018",
        "New Vendor Analysis",
        24,
        63,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL027",
        "Salary Above Approved Salary",
        25,
        62,
        "Priority 2 - Moderate Definition",
    ),
    _entry(
        "GL009",
        "Vendor Concentration Analysis",
        26,
        49,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL019",
        "Split Purchases",
        27,
        47,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL020",
        "Dormant Period Followed by Activity Spike",
        28,
        45,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL025",
        "Negative Balance Review",
        29,
        43,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL026",
        "Unexpected Account Combinations",
        30,
        41,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL029",
        "Payroll Misclassification",
        31,
        39,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL030",
        "Benford's Law Analysis",
        32,
        35,
        "Priority 3 - Significant Definition Work",
    ),
    _entry(
        "GL031",
        "Outlier Detection",
        33,
        33,
        "Priority 3 - Significant Definition Work",
    ),
)

_PROCEDURES_BY_ID = {entry.procedure_id: entry for entry in GENERAL_LEDGER_PROCEDURES}


def get_general_ledger_procedure(
    procedure_id: str,
) -> GeneralLedgerProcedureCatalogueEntry | None:
    """Return a GL catalogue entry by canonical/display identifier."""

    try:
        canonical = canonical_procedure_id(procedure_id)
    except ValueError:
        return None

    return _PROCEDURES_BY_ID.get(canonical)


def require_general_ledger_procedure(
    procedure_id: str,
) -> GeneralLedgerProcedureCatalogueEntry:
    """Return a GL catalogue entry or raise a clear lookup error."""

    canonical = canonical_procedure_id(procedure_id)
    entry = _PROCEDURES_BY_ID.get(canonical)

    if entry is None:
        raise KeyError(f"Unknown General Ledger engine procedure ID: {canonical}")

    return entry
