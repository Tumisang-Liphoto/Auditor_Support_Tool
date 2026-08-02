"""Standard fields and registered General Ledger audit tests."""

from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    AuditFieldDefinition,
    TestDefinition,
)

GENERAL_LEDGER_FIELDS: tuple[AuditFieldDefinition, ...] = (
    AuditFieldDefinition(
        key="transaction_date",
        label="Transaction Date",
        description="The accounting or posting date assigned to the transaction.",
    ),
    AuditFieldDefinition(
        key="invoice_number",
        label="Invoice Number",
        description="The supplier or source invoice reference.",
    ),
    AuditFieldDefinition(
        key="vendor_number",
        label="Vendor Number",
        description="The unique identifier assigned to the supplier or vendor.",
    ),
    AuditFieldDefinition(
        key="vendor_name",
        label="Vendor Name",
        description="The name of the supplier or vendor.",
    ),
    AuditFieldDefinition(
        key="journal_number",
        label="Journal Number",
        description="The journal, document or transaction reference number.",
    ),
    AuditFieldDefinition(
        key="account_code",
        label="Account Code",
        description="The general ledger account affected by the transaction.",
    ),
    AuditFieldDefinition(
        key="description",
        label="Description",
        description="The transaction narration, memo or description.",
    ),
    AuditFieldDefinition(
        key="debit_amount",
        label="Debit Amount",
        description="The debit value recorded for the transaction.",
    ),
    AuditFieldDefinition(
        key="credit_amount",
        label="Credit Amount",
        description="The credit value recorded for the transaction.",
    ),
    AuditFieldDefinition(
        key="net_amount",
        label="Net Amount",
        description="The net or total monetary value of the transaction.",
    ),
    AuditFieldDefinition(
        key="prepared_by",
        label="Prepared By",
        description="The user who entered or prepared the transaction.",
    ),
    AuditFieldDefinition(
        key="approved_by",
        label="Approved By",
        description="The user who approved or authorised the transaction.",
    ),
    AuditFieldDefinition(
        key="source_module",
        label="Source Module",
        description="The application module from which the transaction originated.",
    ),
)

GL_001_DUPLICATE_INVOICES = TestDefinition(
    code="GL-001",
    title="Duplicate Invoice Detection",
    category="General Ledger",
    description=("Identifies repeated invoice numbers that may require further audit scrutiny."),
    required_fields=("invoice_number",),
    helpful_fields=(
        "vendor_number",
        "vendor_name",
        "transaction_date",
        "journal_number",
        "net_amount",
        "debit_amount",
        "credit_amount",
        "description",
        "account_code",
        "prepared_by",
        "approved_by",
        "source_module",
    ),
    logic_version="1.0",
)

GL_003_WEEKEND_POSTINGS = TestDefinition(
    code="GL-003",
    title="Weekend Postings",
    category="General Ledger",
    description=(
        "Identifies transactions dated on Saturdays or Sundays for further audit scrutiny."
    ),
    required_fields=("transaction_date",),
    helpful_fields=(
        "journal_number",
        "account_code",
        "description",
        "debit_amount",
        "credit_amount",
        "net_amount",
        "vendor_number",
        "vendor_name",
        "prepared_by",
        "approved_by",
        "source_module",
    ),
    logic_version="1.0",
)

GENERAL_LEDGER_TESTS: tuple[TestDefinition, ...] = (
    GL_001_DUPLICATE_INVOICES,
    GL_003_WEEKEND_POSTINGS,
)


def get_field_definition(field_key: str) -> AuditFieldDefinition | None:
    """Return a standard field definition by its key."""

    for field_definition in GENERAL_LEDGER_FIELDS:
        if field_definition.key == field_key:
            return field_definition

    return None


def get_test_definition(test_code: str) -> TestDefinition | None:
    """Return a registered General Ledger test by its code."""

    normalised_code = test_code.strip().casefold()

    for test_definition in GENERAL_LEDGER_TESTS:
        if test_definition.code.casefold() == normalised_code:
            return test_definition

    return None
