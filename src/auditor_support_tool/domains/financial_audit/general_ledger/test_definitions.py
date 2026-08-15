"""Standard fields and legacy General Ledger test-definition compatibility.

The authoritative procedure metadata lives in ``procedure_catalogue`` using
the generic core ``ProcedureDefinition`` contract.

The legacy ``TestDefinition`` objects exported here are derived from that
catalogue so older General Ledger services and prototype procedures continue
to work while they are migrated to the Test Engine.
"""

from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    GeneralLedgerProcedureCatalogueEntry,
    require_general_ledger_procedure,
)
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


def _legacy_test_definition(
    entry: GeneralLedgerProcedureCatalogueEntry,
) -> TestDefinition:
    """Return a legacy test-definition view of a catalogue entry."""

    return TestDefinition(
        code=entry.display_id,
        title=entry.name,
        category=entry.category,
        description=entry.description,
        required_fields=entry.required_fields,
        helpful_fields=entry.helpful_fields,
        logic_version=entry.procedure_version,
    )


GL_001_DUPLICATE_INVOICES = _legacy_test_definition(require_general_ledger_procedure("GL001"))

GL_003_WEEKEND_POSTINGS = _legacy_test_definition(require_general_ledger_procedure("GL003"))

GENERAL_LEDGER_TESTS: tuple[TestDefinition, ...] = (
    GL_001_DUPLICATE_INVOICES,
    GL_003_WEEKEND_POSTINGS,
)

_LEGACY_TESTS_BY_CANONICAL_ID = {
    canonical_procedure_id(test_definition.code): test_definition
    for test_definition in GENERAL_LEDGER_TESTS
}


def get_field_definition(
    field_key: str,
) -> AuditFieldDefinition | None:
    """Return a standard field definition by its key."""

    cleaned_key = field_key.strip()

    for field_definition in GENERAL_LEDGER_FIELDS:
        if field_definition.key == cleaned_key:
            return field_definition

    return None


def get_test_definition(
    test_code: str,
) -> TestDefinition | None:
    """Return a legacy test view by canonical or display identifier."""

    try:
        canonical = canonical_procedure_id(test_code)
    except ValueError:
        return None

    return _LEGACY_TESTS_BY_CANONICAL_ID.get(canonical)
