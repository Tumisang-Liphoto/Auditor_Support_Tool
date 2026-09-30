"""GL-011: transaction accounts absent from the supplied Chart of Accounts."""

from decimal import Decimal
from math import isfinite

from auditor_support_tool.core.audit_execution_models import ExecutionCancellationToken
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import AuditRecordSource
from auditor_support_tool.core.prepared_audit_dataset import FieldValueStatus, ResolvedFieldValue
from auditor_support_tool.core.procedure_dataset_resolution import ProcedureDatasetBundle
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)

_GL011_DEFINITION = require_general_ledger_procedure("GL011").definition


class UnmappedAccountsProcedure:
    """Identify each eligible GL record whose account has no COA membership."""

    @property
    def definition(self) -> ProcedureDefinition:
        return _GL011_DEFINITION

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        cancellation_token.raise_if_cancelled()
        if not isinstance(source, ProcedureDatasetBundle):
            raise ValueError(
                "GL011 requires resolved General Ledger and Chart of Accounts datasets."
            )

        ledger = source.require_source("general_ledger")
        reference = source.require_source("chart_of_accounts")
        reference_keys: set[str] = set()
        blank_reference_accounts = 0
        duplicate_reference_accounts = 0

        for record in reference.iter_records():
            cancellation_token.raise_if_cancelled()
            key = _account_key(record.resolve("account_code"))
            if not key:
                blank_reference_accounts += 1
            elif key in reference_keys:
                duplicate_reference_accounts += 1
            else:
                reference_keys.add(key)

        if not reference_keys:
            raise ValueError(
                "GL011 cannot evaluate account membership because the supplied Chart of Accounts "
                "contains no nonblank account identifiers. "
                "Review the reference dataset and mapping."
            )

        exceptions: list[ProcedureExceptionRecord] = []
        unmapped_keys: set[str] = set()
        evaluated = 0
        blank_gl_accounts = 0

        for record in ledger.iter_records():
            cancellation_token.raise_if_cancelled()
            account = record.resolve("account_code")
            key = _account_key(account)
            if not key:
                blank_gl_accounts += 1
                continue

            evaluated += 1
            if key in reference_keys:
                continue

            unmapped_keys.add(key)
            exceptions.append(
                ProcedureExceptionRecord.create(
                    source_record_id=record.source_record_id,
                    source_row_number=record.source_row_number,
                    reason_code="ACCOUNT_NOT_IN_CHART_OF_ACCOUNTS",
                    reason="Account absent from supplied Chart of Accounts; review required.",
                    values={
                        "account_code": account.raw_value,
                        "normalised_account_code": key,
                    },
                )
            )

        limitations = [
            "Existence is tested against the supplied Chart of Accounts; its authority and "
            "completeness require auditor confirmation. Account status (including inactive, "
            "blocked or closed accounts) is not tested.",
            "The full prepared General Ledger population is evaluated, apart from blank account "
            "codes. The recorded audit period does not filter transactions in GL011 version 1.0.",
            "Matching uses original loaded account values as text, with surrounding whitespace "
            "removed and case-insensitive comparison. Leading zeros and punctuation in text "
            "are preserved; formatting or zeros already lost in the source cannot be recovered.",
        ]
        if blank_reference_accounts or duplicate_reference_accounts:
            limitations.append(
                f"The reference contains {blank_reference_accounts} blank account record(s) "
                f"and {duplicate_reference_accounts} duplicate account record(s) beyond the "
                "first occurrence. Blanks are ignored and duplicates do not change membership."
            )
        return ProcedureResult.create(
            context=context,
            population_count=ledger.record_count,
            records_evaluated_count=evaluated,
            exception_records=tuple(exceptions),
            exclusion_counts={"blank_account_code": blank_gl_accounts} if blank_gl_accounts else {},
            limitations=tuple(limitations),
            metrics={
                "unique_unmapped_account_count": len(unmapped_keys),
                "unique_reference_account_count": len(reference_keys),
                "reference_record_count": reference.record_count,
                "blank_reference_account_count": blank_reference_accounts,
                "duplicate_reference_account_count": duplicate_reference_accounts,
                "reference_dataset_id": reference.dataset_id,
            },
        )


def _account_key(account: ResolvedFieldValue) -> str:
    """Use mapped original identifiers, never numerically converted prepared values."""

    if account.status == FieldValueStatus.BLANK:
        return ""
    raw = account.raw_value
    if account.status == FieldValueStatus.UNMAPPED or raw is None:
        raise ValueError("A required account identifier could not be resolved from its source row.")
    # Preparation may convert '00120' to 120 or reject an alphanumeric code under a
    # numeric type. Neither conversion defines account identity for this existence rule.
    if isinstance(raw, str):
        return raw.strip().casefold()
    if (
        isinstance(raw, bool)
        or not isinstance(raw, (int, float, Decimal))
        or (isinstance(raw, float) and not isfinite(raw))
        or (isinstance(raw, Decimal) and not raw.is_finite())
    ):
        raise ValueError("Account identifiers must be text or finite numbers; review source data.")
    return str(raw).casefold()
