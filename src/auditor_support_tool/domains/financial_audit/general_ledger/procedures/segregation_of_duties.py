"""GL-006 Segregation of Duties procedure."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from auditor_support_tool.core.audit_execution_models import (
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecord,
    AuditRecordSource,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    FieldValueStatus,
    ResolvedFieldValue,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)

_GL006_DEFINITION = require_general_ledger_procedure("GL006").definition

_REASON_CODE = "SAME_ENTRY_AND_APPROVAL_USER"
_REASON_TEXT = "Same user entered and approved transaction - further audit scrutiny required."


@dataclass(slots=True)
class _UserSelfApprovalStats:
    """Descriptive statistics for one normalised self-approving user."""

    display_user: str
    self_approvals: int = 0
    journals: set[str] = field(default_factory=set)
    accounts: set[str] = field(default_factory=set)
    transaction_amount_total: Decimal = Decimal("0")
    transaction_amount_records: int = 0


class SegregationOfDutiesProcedure:
    """Identify records entered and approved by the same mapped user."""

    @property
    def definition(self) -> ProcedureDefinition:
        """Return the authoritative GL-006 definition."""

        return _GL006_DEFINITION

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        """Execute the approved GL-006 version 1.0 same-user rule."""

        exceptions: list[ProcedureExceptionRecord] = []
        records_evaluated = 0

        blank_entry_users = 0
        blank_approval_users = 0
        invalid_entry_users = 0
        invalid_approval_users = 0

        affected_journals: set[str] = set()
        affected_accounts: set[str] = set()
        user_stats: dict[str, _UserSelfApprovalStats] = {}

        helpful_availability: dict[str, bool] | None = None

        for record in source.iter_records():
            cancellation_token.raise_if_cancelled()

            if helpful_availability is None:
                helpful_availability = self._helpful_field_availability(record)

            entry_user = record.resolve("entry_user")
            approval_user = record.resolve("approval_user")

            if entry_user.status == FieldValueStatus.BLANK:
                blank_entry_users += 1
                continue

            if entry_user.status != FieldValueStatus.VALID:
                invalid_entry_users += 1
                continue

            if approval_user.status == FieldValueStatus.BLANK:
                blank_approval_users += 1
                continue

            if approval_user.status != FieldValueStatus.VALID:
                invalid_approval_users += 1
                continue

            normalised_entry = self._normalise_user(entry_user.value)
            normalised_approval = self._normalise_user(approval_user.value)

            if not normalised_entry:
                blank_entry_users += 1
                continue

            if not normalised_approval:
                blank_approval_users += 1
                continue

            records_evaluated += 1

            if normalised_entry != normalised_approval:
                continue

            resolved_helpful = {
                field_key: record.resolve(field_key) for field_key in self.definition.helpful_fields
            }

            journal_value = self._resolved_text(resolved_helpful.get("journal_number"))
            account_value = self._resolved_text(resolved_helpful.get("account_code"))
            transaction_amount = self._resolved_decimal(resolved_helpful.get("transaction_amount"))

            if journal_value:
                affected_journals.add(journal_value.casefold())

            if account_value:
                affected_accounts.add(account_value.casefold())

            display_user = self._resolved_text(entry_user) or normalised_entry
            stats = user_stats.get(normalised_entry)

            if stats is None:
                stats = _UserSelfApprovalStats(display_user=display_user)
                user_stats[normalised_entry] = stats

            stats.self_approvals += 1

            if journal_value:
                stats.journals.add(journal_value.casefold())

            if account_value:
                stats.accounts.add(account_value.casefold())

            if transaction_amount is not None:
                stats.transaction_amount_total += transaction_amount
                stats.transaction_amount_records += 1

            exceptions.append(
                ProcedureExceptionRecord.create(
                    source_record_id=record.source_record_id,
                    source_row_number=record.source_row_number,
                    reason_code=_REASON_CODE,
                    reason=_REASON_TEXT,
                    values=self._exception_values(
                        entry_user=entry_user,
                        approval_user=approval_user,
                        normalised_user=normalised_entry,
                        resolved_helpful=resolved_helpful,
                    ),
                )
            )

        if helpful_availability is None:
            helpful_availability = {
                "journal_number": False,
                "account_code": False,
                "transaction_amount": False,
            }

        exclusion_counts: dict[str, int] = {}

        if blank_entry_users:
            exclusion_counts["blank_entry_user"] = blank_entry_users

        if blank_approval_users:
            exclusion_counts["blank_approval_user"] = blank_approval_users

        if invalid_entry_users:
            exclusion_counts["invalid_entry_user"] = invalid_entry_users

        if invalid_approval_users:
            exclusion_counts["invalid_approval_user"] = invalid_approval_users

        limitations = [
            "System, service and shared accounts are not automatically excluded "
            "in GL-006 version 1.0; auditor review is required."
        ]

        invalid_user_records = invalid_entry_users + invalid_approval_users

        if invalid_user_records:
            limitations.append(
                f"{invalid_user_records:,} record"
                + ("" if invalid_user_records == 1 else "s")
                + " contained unusable user data and were excluded from evaluation."
            )

        user_analysis = self._user_analysis(
            user_stats=user_stats,
            exception_count=len(exceptions),
        )

        top_user = user_analysis[0] if user_analysis else None

        return ProcedureResult.create(
            context=context,
            population_count=source.record_count,
            records_evaluated_count=records_evaluated,
            exception_records=tuple(exceptions),
            exclusion_counts=exclusion_counts,
            limitations=tuple(limitations),
            metrics={
                "same_user_exceptions": len(exceptions),
                "distinct_conflicting_users": len(user_stats),
                "highest_self_approval_count": (int(top_user["self_approvals"]) if top_user else 0),
                "top_user": str(top_user["user"]) if top_user else "",
                "top_user_concentration_pct": (
                    float(top_user["exception_share_pct"]) if top_user else 0.0
                ),
                "user_self_approval_analysis": user_analysis,
                "journal_number_available": helpful_availability.get(
                    "journal_number",
                    False,
                ),
                "affected_journals": len(affected_journals),
                "account_code_available": helpful_availability.get(
                    "account_code",
                    False,
                ),
                "affected_accounts": len(affected_accounts),
                "transaction_amount_available": helpful_availability.get(
                    "transaction_amount",
                    False,
                ),
                "blank_entry_user_count": blank_entry_users,
                "blank_approval_user_count": blank_approval_users,
                "invalid_entry_user_count": invalid_entry_users,
                "invalid_approval_user_count": invalid_approval_users,
            },
        )

    def _exception_values(
        self,
        *,
        entry_user: ResolvedFieldValue,
        approval_user: ResolvedFieldValue,
        normalised_user: str,
        resolved_helpful: dict[str, ResolvedFieldValue],
    ) -> dict[str, object]:
        """Return source-linked values useful for SoD review."""

        values: dict[str, object] = {
            "entry_user": self._resolved_text(entry_user) or "",
            "approval_user": self._resolved_text(approval_user) or "",
            "normalised_user": normalised_user,
        }

        for field_key in self.definition.helpful_fields:
            resolved = resolved_helpful[field_key]

            if resolved.is_usable:
                values[field_key] = resolved.value

        return values

    @staticmethod
    def _user_analysis(
        *,
        user_stats: dict[str, _UserSelfApprovalStats],
        exception_count: int,
    ) -> tuple[dict[str, object], ...]:
        """Return ranked descriptive analysis of self-approval by user."""

        rows: list[dict[str, object]] = []

        for normalised_user, stats in user_stats.items():
            share = (stats.self_approvals / exception_count) * 100.0 if exception_count else 0.0

            rows.append(
                {
                    "user": stats.display_user,
                    "normalised_user": normalised_user,
                    "self_approvals": stats.self_approvals,
                    "exception_share_pct": share,
                    "affected_journals": len(stats.journals),
                    "affected_accounts": len(stats.accounts),
                    "transaction_amount_total": stats.transaction_amount_total,
                    "transaction_amount_records": stats.transaction_amount_records,
                }
            )

        rows.sort(
            key=lambda row: (
                -int(row["self_approvals"]),
                str(row["normalised_user"]),
            )
        )

        return tuple(rows)

    @staticmethod
    def _normalise_user(value: object | None) -> str:
        """Return the version 1.0 user comparison value."""

        if value is None:
            return ""

        return str(value).strip().casefold()

    @staticmethod
    def _resolved_text(
        resolved: ResolvedFieldValue | None,
    ) -> str | None:
        """Return trimmed text from one usable resolved value."""

        if resolved is None or not resolved.is_usable:
            return None

        text = str(resolved.value).strip()

        return text or None

    @staticmethod
    def _resolved_decimal(
        resolved: ResolvedFieldValue | None,
    ) -> Decimal | None:
        """Return a Decimal from one usable monetary value."""

        if resolved is None or not resolved.is_usable or resolved.value is None:
            return None

        if isinstance(resolved.value, Decimal):
            return resolved.value

        try:
            return Decimal(str(resolved.value).strip())
        except InvalidOperation, ValueError:
            return None

    @staticmethod
    def _helpful_field_availability(
        record: AuditRecord,
    ) -> dict[str, bool]:
        """Return structural availability of optional summary fields."""

        return {
            field_key: (record.resolve(field_key).status != FieldValueStatus.UNMAPPED)
            for field_key in (
                "journal_number",
                "account_code",
                "transaction_amount",
            )
        }
