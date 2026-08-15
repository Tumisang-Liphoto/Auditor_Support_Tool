"""GL-003 Weekend Transactions procedure."""

from __future__ import annotations

from datetime import date, datetime

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
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)

_GL003_DEFINITION = require_general_ledger_procedure("GL003").definition


class WeekendTransactionsProcedure:
    """Identify transactions dated on Saturdays or Sundays."""

    @property
    def definition(self) -> ProcedureDefinition:
        """Return the authoritative GL-003 definition."""

        return _GL003_DEFINITION

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        """Execute GL-003 against the complete prepared population."""

        exceptions: list[ProcedureExceptionRecord] = []

        blank_dates = 0
        invalid_dates = 0
        outside_audit_period = 0

        records_evaluated = 0
        saturday_transactions = 0
        sunday_transactions = 0
        weekend_dates: set[date] = set()

        period_start = self._audit_period_start(context)
        period_end = self._audit_period_end(context)

        for record in source.iter_records():
            cancellation_token.raise_if_cancelled()

            resolved_date = record.resolve("transaction_date")

            if resolved_date.status == FieldValueStatus.BLANK:
                blank_dates += 1
                continue

            if resolved_date.status != FieldValueStatus.VALID:
                invalid_dates += 1
                continue

            transaction_date = self._as_date(resolved_date.value)

            if transaction_date is None:
                invalid_dates += 1
                continue

            if (
                period_start is not None
                and period_end is not None
                and not (period_start <= transaction_date <= period_end)
            ):
                outside_audit_period += 1
                continue

            records_evaluated += 1

            weekday_number = transaction_date.weekday()

            if weekday_number not in {
                5,
                6,
            }:
                continue

            if weekday_number == 5:
                day_name = "Saturday"
                saturday_transactions += 1
            else:
                day_name = "Sunday"
                sunday_transactions += 1

            weekend_dates.add(transaction_date)

            exceptions.append(
                ProcedureExceptionRecord.create(
                    source_record_id=(record.source_record_id),
                    source_row_number=(record.source_row_number),
                    reason_code="WEEKEND_TRANSACTION",
                    reason=(f"Transaction date falls on {day_name}."),
                    values=self._exception_values(
                        record=record,
                        transaction_date=transaction_date,
                        day_name=day_name,
                    ),
                )
            )

        exclusion_counts: dict[str, int] = {}

        if blank_dates:
            exclusion_counts["blank_transaction_date"] = blank_dates

        if invalid_dates:
            exclusion_counts["invalid_transaction_date"] = invalid_dates

        if outside_audit_period:
            exclusion_counts["outside_audit_period"] = outside_audit_period

        limitations: tuple[str, ...] = ()

        if not context.has_audit_period:
            limitations = (
                "No audit period was supplied. "
                "All usable transaction dates in the source "
                "population were evaluated.",
            )

        return ProcedureResult.create(
            context=context,
            population_count=source.record_count,
            records_evaluated_count=records_evaluated,
            exception_records=tuple(exceptions),
            exclusion_counts=exclusion_counts,
            limitations=limitations,
            metrics={
                "weekend_transactions": len(exceptions),
                "saturday_transactions": (saturday_transactions),
                "sunday_transactions": (sunday_transactions),
                "distinct_weekend_dates": len(weekend_dates),
            },
        )

    def _exception_values(
        self,
        *,
        record: AuditRecord,
        transaction_date: date,
        day_name: str,
    ) -> dict[str, object]:
        """Return standard-field values useful for exception review."""

        values: dict[str, object] = {
            "transaction_date": (transaction_date.isoformat()),
            "day_of_week": day_name,
        }

        for field_key in self.definition.helpful_fields:
            resolved = record.resolve(field_key)

            if resolved.is_usable:
                values[field_key] = resolved.value

        return values

    @staticmethod
    def _as_date(
        value: object | None,
    ) -> date | None:
        """Return a date from an already resolved audit value."""

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        return None

    @staticmethod
    def _audit_period_start(
        context: ProcedureRunContext,
    ) -> date | None:
        """Return the validated audit-period start when available."""

        if not context.has_audit_period:
            return None

        return date.fromisoformat(context.audit_period_start)

    @staticmethod
    def _audit_period_end(
        context: ProcedureRunContext,
    ) -> date | None:
        """Return the validated audit-period end when available."""

        if not context.has_audit_period:
            return None

        return date.fromisoformat(context.audit_period_end)
