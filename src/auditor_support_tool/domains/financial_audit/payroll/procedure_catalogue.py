"""Authoritative metadata for executable payroll audit procedures."""

from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
    ProcedureParameterType,
)
from auditor_support_tool.core.workbook_package import DatasetType

PAY001_DEFINITION = ProcedureDefinition.create(
    procedure_id="PAY001",
    name="Payroll GL Employee Validation",
    category="Payroll / Financial Audit",
    description=(
        "Identifies payroll-related General Ledger postings with an unmatched employee "
        "identifier or a current Employee Master status other than Active."
    ),
    audit_objective=(
        "Select General Ledger postings whose descriptions match the configured payroll "
        "descriptions and compare usable employee identifiers with the supplied Employee Master."
    ),
    isa_references=("ISA 500, paragraphs 6 and 9",),
    isa_basis_type="Deterministic audit methodology",
    audit_rationale=(
        "The procedure supports auditor evaluation of payroll-related ledger activity by "
        "performing an exact, reproducible employee-master comparison. ISA 500 provides general "
        "audit-evidence context but does not prescribe this algorithm."
    ),
    result_meaning=(
        "An exception is a payroll-related General Ledger record with a usable employee "
        "identifier that is absent from the supplied Employee Master, or that matches an "
        "employee whose current Employment Status is not Active. It requires auditor review "
        "and does not by itself establish fraud, error, non-compliance, or an audit finding."
    ),
    limitations=(
        "Description selection is exact after trimming surrounding whitespace and ignoring case; "
        "the configured descriptions determine the procedure population.",
        "Employee identifiers are compared as identifiers after trimming surrounding whitespace "
        "and ignoring case. Leading zeroes and punctuation are preserved; no fuzzy, substring, "
        "or numeric-equivalence matching is performed.",
        "Blank General Ledger employee identifiers, ambiguous Employee Master identifiers, and "
        "matched employees with unusable status are exclusions and data-quality observations, "
        "not exceptions.",
        "Employment Status is the current status in the supplied master. Without effective dates, "
        "PAY001 does not determine whether a posting occurred after termination or suspension.",
        "Version 1.0 evaluates the full prepared General Ledger population when selecting payroll "
        "descriptions; the recorded audit period does not filter PAY001 records.",
        "General Ledger source rows remain the exception records; Employee Master values are "
        "supporting reference evidence. Bank account and salary values do not affect membership.",
    ),
    dataset_requirements=(
        ProcedureDatasetRequirement.create(
            role="general_ledger",
            dataset_type=DatasetType.GENERAL_LEDGER,
            required_fields=("transaction_description", "employee_number"),
            helpful_fields=(
                "transaction_date",
                "journal_number",
                "account_code",
                "debit_amount",
                "credit_amount",
                "transaction_amount",
                "cost_centre_code",
            ),
            primary=True,
        ),
        ProcedureDatasetRequirement.create(
            role="employee_master",
            dataset_type=DatasetType.EMPLOYEE_MASTER,
            required_fields=("employee_id", "employment_status"),
            helpful_fields=("employee_name", "department_code", "department_name"),
        ),
    ),
    parameter_definitions=(
        ProcedureParameterDefinition.create(
            key="payroll_descriptions",
            label="Payroll descriptions",
            value_type=ProcedureParameterType.TEXT_LIST,
            description=(
                "Exact General Ledger descriptions included in the payroll-related population. "
                "Matching ignores surrounding whitespace and case."
            ),
            required=True,
            default_value=(
                "Monthly salary allocation",
                "Payroll expense posting",
                "Overtime payroll posting",
            ),
            placeholder="Separate descriptions with commas or new lines",
        ),
    ),
    procedure_version="1.0",
)
