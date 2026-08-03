"""Standard audit-field definitions used during field mapping."""

from dataclasses import dataclass

from auditor_support_tool.core.workbook_package import (
    DatasetType,
)


@dataclass(frozen=True, slots=True)
class StandardAuditField:
    """One standard field expected by later audit procedures."""

    key: str
    display_name: str
    description: str
    required: bool = False


GENERAL_LEDGER_FIELDS: tuple[StandardAuditField, ...] = (
    StandardAuditField(
        key="transaction_id",
        display_name="Transaction ID",
        description=("Unique identifier for the accounting transaction or journal line."),
    ),
    StandardAuditField(
        key="journal_number",
        display_name="Journal Number",
        description=("Journal, voucher or document reference assigned to the accounting entry."),
    ),
    StandardAuditField(
        key="transaction_date",
        display_name="Transaction Date",
        description=("Date on which the transaction was recorded or posted."),
        required=True,
    ),
    StandardAuditField(
        key="posting_date",
        display_name="Posting Date",
        description=("Date on which the transaction was posted to the ledger."),
    ),
    StandardAuditField(
        key="account_code",
        display_name="Account Code",
        description=("Code identifying the general-ledger account."),
        required=True,
    ),
    StandardAuditField(
        key="account_name",
        display_name="Account Name",
        description=("Description or name of the general-ledger account."),
    ),
    StandardAuditField(
        key="description",
        display_name="Transaction Description",
        description=("Narration or description attached to the transaction."),
    ),
    StandardAuditField(
        key="debit_amount",
        display_name="Debit Amount",
        description=("Debit value recorded for the transaction."),
    ),
    StandardAuditField(
        key="credit_amount",
        display_name="Credit Amount",
        description=("Credit value recorded for the transaction."),
    ),
    StandardAuditField(
        key="amount",
        display_name="Transaction Amount",
        description=(
            "Signed or unsigned transaction value where separate "
            "debit and credit fields are not provided."
        ),
    ),
    StandardAuditField(
        key="invoice_number",
        display_name="Invoice Number",
        description=("Supplier or customer invoice reference."),
    ),
    StandardAuditField(
        key="vendor_code",
        display_name="Vendor Code",
        description=("Code identifying the supplier or vendor."),
    ),
    StandardAuditField(
        key="vendor_name",
        display_name="Vendor Name",
        description=("Name of the supplier or vendor."),
    ),
    StandardAuditField(
        key="customer_code",
        display_name="Customer Code",
        description=("Code identifying the customer."),
    ),
    StandardAuditField(
        key="customer_name",
        display_name="Customer Name",
        description=("Name of the customer."),
    ),
    StandardAuditField(
        key="user_id",
        display_name="User ID",
        description=("User account that created, entered or posted the transaction."),
    ),
    StandardAuditField(
        key="entry_timestamp",
        display_name="Entry Timestamp",
        description=("Date and time when the transaction was created or entered."),
    ),
    StandardAuditField(
        key="approval_user",
        display_name="Approval User",
        description=("User who approved or authorised the transaction."),
    ),
    StandardAuditField(
        key="approval_date",
        display_name="Approval Date",
        description=("Date on which the transaction was approved."),
    ),
    StandardAuditField(
        key="currency",
        display_name="Currency",
        description=("Currency code applicable to the transaction."),
    ),
    StandardAuditField(
        key="period",
        display_name="Accounting Period",
        description=("Accounting period to which the transaction relates."),
    ),
)


CHART_OF_ACCOUNTS_FIELDS: tuple[StandardAuditField, ...] = (
    StandardAuditField(
        key="account_code",
        display_name="Account Code",
        description="Unique general-ledger account code.",
        required=True,
    ),
    StandardAuditField(
        key="account_name",
        display_name="Account Name",
        description="General-ledger account name or description.",
        required=True,
    ),
    StandardAuditField(
        key="account_type",
        display_name="Account Type",
        description=("Classification such as asset, liability, income or expense."),
    ),
    StandardAuditField(
        key="parent_account",
        display_name="Parent Account",
        description="Parent or control account code.",
    ),
    StandardAuditField(
        key="active_status",
        display_name="Active Status",
        description="Whether the account is active or inactive.",
    ),
)


VENDOR_MASTER_FIELDS: tuple[StandardAuditField, ...] = (
    StandardAuditField(
        key="vendor_code",
        display_name="Vendor Code",
        description="Unique supplier or vendor identifier.",
        required=True,
    ),
    StandardAuditField(
        key="vendor_name",
        display_name="Vendor Name",
        description="Registered supplier or vendor name.",
        required=True,
    ),
    StandardAuditField(
        key="tax_number",
        display_name="Tax Number",
        description="Supplier tax or registration number.",
    ),
    StandardAuditField(
        key="bank_account",
        display_name="Bank Account",
        description="Supplier bank-account number.",
    ),
    StandardAuditField(
        key="bank_name",
        display_name="Bank Name",
        description="Supplier bank name.",
    ),
    StandardAuditField(
        key="branch_code",
        display_name="Branch Code",
        description="Supplier bank branch code.",
    ),
    StandardAuditField(
        key="address",
        display_name="Address",
        description="Supplier physical or postal address.",
    ),
    StandardAuditField(
        key="email",
        display_name="Email Address",
        description="Supplier email address.",
    ),
    StandardAuditField(
        key="telephone",
        display_name="Telephone Number",
        description="Supplier contact number.",
    ),
    StandardAuditField(
        key="active_status",
        display_name="Active Status",
        description="Whether the supplier account is active.",
    ),
)


CUSTOMER_MASTER_FIELDS: tuple[StandardAuditField, ...] = (
    StandardAuditField(
        key="customer_code",
        display_name="Customer Code",
        description="Unique customer identifier.",
        required=True,
    ),
    StandardAuditField(
        key="customer_name",
        display_name="Customer Name",
        description="Registered customer name.",
        required=True,
    ),
    StandardAuditField(
        key="tax_number",
        display_name="Tax Number",
        description="Customer tax or registration number.",
    ),
    StandardAuditField(
        key="address",
        display_name="Address",
        description="Customer physical or postal address.",
    ),
    StandardAuditField(
        key="email",
        display_name="Email Address",
        description="Customer email address.",
    ),
    StandardAuditField(
        key="telephone",
        display_name="Telephone Number",
        description="Customer contact number.",
    ),
    StandardAuditField(
        key="credit_limit",
        display_name="Credit Limit",
        description="Approved customer credit limit.",
    ),
    StandardAuditField(
        key="active_status",
        display_name="Active Status",
        description="Whether the customer account is active.",
    ),
)


USER_ACCESS_FIELDS: tuple[StandardAuditField, ...] = (
    StandardAuditField(
        key="user_id",
        display_name="User ID",
        description="Unique application or database user identifier.",
        required=True,
    ),
    StandardAuditField(
        key="user_name",
        display_name="User Name",
        description="Name assigned to the user account.",
    ),
    StandardAuditField(
        key="role",
        display_name="Role",
        description="Role or access group assigned to the user.",
        required=True,
    ),
    StandardAuditField(
        key="account_status",
        display_name="Account Status",
        description="Whether the account is active, disabled or locked.",
    ),
    StandardAuditField(
        key="created_date",
        display_name="Created Date",
        description="Date on which the account was created.",
    ),
    StandardAuditField(
        key="last_login",
        display_name="Last Login",
        description="Most recent recorded login date or timestamp.",
    ),
    StandardAuditField(
        key="department",
        display_name="Department",
        description="Department or organisational unit of the user.",
    ),
)


FIELD_CATALOGUES: dict[
    DatasetType,
    tuple[StandardAuditField, ...],
] = {
    DatasetType.GENERAL_LEDGER: GENERAL_LEDGER_FIELDS,
    DatasetType.JOURNAL_LISTING: GENERAL_LEDGER_FIELDS,
    DatasetType.CHART_OF_ACCOUNTS: CHART_OF_ACCOUNTS_FIELDS,
    DatasetType.VENDOR_MASTER: VENDOR_MASTER_FIELDS,
    DatasetType.CUSTOMER_MASTER: CUSTOMER_MASTER_FIELDS,
    DatasetType.USER_ACCESS_LISTING: USER_ACCESS_FIELDS,
}


def fields_for_dataset_type(
    dataset_type: DatasetType,
) -> tuple[StandardAuditField, ...]:
    """Return the standard-field catalogue for a dataset type."""

    return FIELD_CATALOGUES.get(dataset_type, ())
