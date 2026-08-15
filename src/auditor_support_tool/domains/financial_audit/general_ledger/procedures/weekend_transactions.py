"""GL-003 Weekend Transactions procedure."""

from __future__ import annotations

from datetime import date, datetime
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

_GL003_DEFINITION = require_general_ledger_procedure("GL003").definition

_HIGH_VALUE_INDICATOR = "high_value"
_MANUAL_JOURNAL_INDICATOR = "manual_journal"
_SAME_USER_INDICATOR = "same_preparer_approver"


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

        saturday_debit_total = Decimal("0")
        saturday_credit_total = Decimal("0")
        sunday_debit_total = Decimal("0")
        sunday_credit_total = Decimal("0")

        high_value_count = 0
        manual_journal_count = 0
        same_user_count = 0
        high_risk_count = 0
        additional_risk_flag_count = 0

        high_value_records_evaluated = 0
        manual_journal_records_evaluated = 0
        same_user_records_evaluated = 0

        debit_values_summarised = 0
        credit_values_summarised = 0

        period_start = self._audit_period_start(context)
        period_end = self._audit_period_end(context)

        high_value_threshold = self._high_value_threshold(context)
        manual_journal_values = self._manual_journal_values(context)

        field_availability: dict[str, bool] | None = None

        for record in source.iter_records():
            cancellation_token.raise_if_cancelled()

            if field_availability is None:
                field_availability = self._field_availability(record)

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

            resolved_helpful = {
                field_key: record.resolve(field_key) for field_key in self.definition.helpful_fields
            }

            debit_amount = self._resolved_decimal(resolved_helpful.get("debit_amount"))
            credit_amount = self._resolved_decimal(resolved_helpful.get("credit_amount"))

            if debit_amount is not None:
                debit_values_summarised += 1

                if day_name == "Saturday":
                    saturday_debit_total += debit_amount
                else:
                    sunday_debit_total += debit_amount

            if credit_amount is not None:
                credit_values_summarised += 1

                if day_name == "Saturday":
                    saturday_credit_total += credit_amount
                else:
                    sunday_credit_total += credit_amount

            risk_indicators: list[str] = []

            amount_for_risk = self._amount_for_risk(resolved_helpful)

            high_value_available = self._high_value_available(
                threshold=high_value_threshold,
                field_availability=field_availability,
            )

            if high_value_available and amount_for_risk is not None:
                high_value_records_evaluated += 1

                if abs(amount_for_risk) >= high_value_threshold:
                    high_value_count += 1
                    risk_indicators.append(_HIGH_VALUE_INDICATOR)

            manual_available = self._manual_journal_available(
                manual_values=manual_journal_values,
                field_availability=field_availability,
            )

            if manual_available:
                manual_value = self._manual_journal_value(resolved_helpful)

                if manual_value is not None:
                    manual_journal_records_evaluated += 1

                    if manual_value.casefold() in manual_journal_values:
                        manual_journal_count += 1
                        risk_indicators.append(_MANUAL_JOURNAL_INDICATOR)

            same_user_available = self._same_user_available(field_availability)

            if same_user_available:
                entry_user = self._resolved_text(resolved_helpful.get("entry_user"))
                approval_user = self._resolved_text(resolved_helpful.get("approval_user"))

                if entry_user is not None and approval_user is not None:
                    same_user_records_evaluated += 1

                    if entry_user.casefold() == approval_user.casefold():
                        same_user_count += 1
                        risk_indicators.append(_SAME_USER_INDICATOR)

            if risk_indicators:
                high_risk_count += 1
                additional_risk_flag_count += len(risk_indicators)

            exceptions.append(
                ProcedureExceptionRecord.create(
                    source_record_id=record.source_record_id,
                    source_row_number=record.source_row_number,
                    reason_code="WEEKEND_TRANSACTION",
                    reason=f"Transaction date falls on {day_name}.",
                    values=self._exception_values(
                        resolved_values=resolved_helpful,
                        transaction_date=transaction_date,
                        day_name=day_name,
                        risk_indicators=tuple(risk_indicators),
                    ),
                )
            )

        if field_availability is None:
            field_availability = {field_key: False for field_key in self.definition.helpful_fields}

        exclusion_counts: dict[str, int] = {}

        if blank_dates:
            exclusion_counts["blank_transaction_date"] = blank_dates

        if invalid_dates:
            exclusion_counts["invalid_transaction_date"] = invalid_dates

        if outside_audit_period:
            exclusion_counts["outside_audit_period"] = outside_audit_period

        high_value_available = self._high_value_available(
            threshold=high_value_threshold,
            field_availability=field_availability,
        )
        manual_available = self._manual_journal_available(
            manual_values=manual_journal_values,
            field_availability=field_availability,
        )
        same_user_available = self._same_user_available(field_availability)

        evaluated_risk_indicators = tuple(
            indicator
            for indicator, available in (
                (
                    _HIGH_VALUE_INDICATOR,
                    high_value_available,
                ),
                (
                    _MANUAL_JOURNAL_INDICATOR,
                    manual_available,
                ),
                (
                    _SAME_USER_INDICATOR,
                    same_user_available,
                ),
            )
            if available
        )

        unavailable_risk_indicators = tuple(
            indicator
            for indicator in (
                _HIGH_VALUE_INDICATOR,
                _MANUAL_JOURNAL_INDICATOR,
                _SAME_USER_INDICATOR,
            )
            if indicator not in evaluated_risk_indicators
        )

        limitations = self._limitations(
            context=context,
            field_availability=field_availability,
            high_value_threshold=high_value_threshold,
            manual_journal_values=manual_journal_values,
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
                "saturday_transactions": saturday_transactions,
                "sunday_transactions": sunday_transactions,
                "distinct_weekend_dates": len(weekend_dates),
                "weekend_percentage": (
                    (len(exceptions) / records_evaluated) * 100.0 if records_evaluated else 0.0
                ),
                "debit_summary_available": field_availability.get(
                    "debit_amount",
                    False,
                ),
                "credit_summary_available": field_availability.get(
                    "credit_amount",
                    False,
                ),
                "debit_values_summarised": debit_values_summarised,
                "credit_values_summarised": credit_values_summarised,
                "saturday_debit_total": saturday_debit_total,
                "saturday_credit_total": saturday_credit_total,
                "sunday_debit_total": sunday_debit_total,
                "sunday_credit_total": sunday_credit_total,
                "weekend_debit_total": (saturday_debit_total + sunday_debit_total),
                "weekend_credit_total": (saturday_credit_total + sunday_credit_total),
                "high_value_available": high_value_available,
                "high_value_threshold": high_value_threshold,
                "high_value_weekend_count": high_value_count,
                "high_value_records_evaluated": (high_value_records_evaluated),
                "manual_journal_available": manual_available,
                "manual_journal_values": tuple(sorted(manual_journal_values)),
                "manual_journal_weekend_count": (manual_journal_count),
                "manual_journal_records_evaluated": (manual_journal_records_evaluated),
                "same_preparer_approver_available": (same_user_available),
                "same_preparer_approver_count": (same_user_count),
                "same_preparer_approver_records_evaluated": (same_user_records_evaluated),
                "high_risk_available": bool(evaluated_risk_indicators),
                "high_risk_weekend_count": high_risk_count,
                "additional_risk_flag_count": (additional_risk_flag_count),
                "evaluated_risk_indicators": (evaluated_risk_indicators),
                "unavailable_risk_indicators": (unavailable_risk_indicators),
            },
        )

    def _field_availability(
        self,
        record: AuditRecord,
    ) -> dict[str, bool]:
        """Return structural mapping availability for helpful fields."""

        return {
            field_key: (record.resolve(field_key).status != FieldValueStatus.UNMAPPED)
            for field_key in self.definition.helpful_fields
        }

    def _exception_values(
        self,
        *,
        resolved_values: dict[str, ResolvedFieldValue],
        transaction_date: date,
        day_name: str,
        risk_indicators: tuple[str, ...],
    ) -> dict[str, object]:
        """Return standard-field values useful for exception review."""

        values: dict[str, object] = {
            "transaction_date": transaction_date.isoformat(),
            "day_of_week": day_name,
        }

        for field_key in self.definition.helpful_fields:
            resolved = resolved_values[field_key]

            if resolved.is_usable:
                values[field_key] = resolved.value

        values["risk_indicators"] = risk_indicators
        values["risk_indicator_count"] = len(risk_indicators)
        values["high_risk"] = bool(risk_indicators)

        return values

    @staticmethod
    def _high_value_threshold(
        context: ProcedureRunContext,
    ) -> Decimal | None:
        """Return a validated optional high-value overlay threshold."""

        raw_value = context.parameters.get("high_value_threshold")

        if raw_value is None or str(raw_value).strip() == "":
            return None

        try:
            threshold = Decimal(str(raw_value).strip())
        except InvalidOperation as error:
            raise ValueError("GL-003 high-value threshold must be numeric.") from error

        if threshold <= 0:
            raise ValueError("GL-003 high-value threshold must be greater than zero.")

        return threshold

    @staticmethod
    def _manual_journal_values(
        context: ProcedureRunContext,
    ) -> frozenset[str]:
        """Return configured values identifying manual journals."""

        raw_values = context.parameters.get("manual_journal_values")

        if raw_values is None:
            return frozenset()

        if isinstance(raw_values, str):
            candidates = raw_values.split(",")
        elif isinstance(
            raw_values,
            (tuple, list, set, frozenset),
        ):
            candidates = raw_values
        else:
            raise ValueError(
                "GL-003 manual journal values must be text or a collection of text values."
            )

        return frozenset(
            str(value).strip().casefold() for value in candidates if str(value).strip()
        )

    @staticmethod
    def _high_value_available(
        *,
        threshold: Decimal | None,
        field_availability: dict[str, bool],
    ) -> bool:
        """Return whether the high-value overlay can be evaluated."""

        if threshold is None:
            return False

        return bool(
            field_availability.get(
                "transaction_amount",
                False,
            )
            or field_availability.get(
                "debit_amount",
                False,
            )
            or field_availability.get(
                "credit_amount",
                False,
            )
        )

    @staticmethod
    def _manual_journal_available(
        *,
        manual_values: frozenset[str],
        field_availability: dict[str, bool],
    ) -> bool:
        """Return whether the manual-journal overlay can be evaluated."""

        if not manual_values:
            return False

        return bool(
            field_availability.get(
                "journal_type",
                False,
            )
            or field_availability.get(
                "journal_source",
                False,
            )
        )

    @staticmethod
    def _same_user_available(
        field_availability: dict[str, bool],
    ) -> bool:
        """Return whether same-preparer/approver analysis is available."""

        return bool(
            field_availability.get(
                "entry_user",
                False,
            )
            and field_availability.get(
                "approval_user",
                False,
            )
        )

    @classmethod
    def _amount_for_risk(
        cls,
        resolved_values: dict[str, ResolvedFieldValue],
    ) -> Decimal | None:
        """Return a comparable signed amount for a weekend record."""

        transaction_amount = cls._resolved_decimal(resolved_values.get("transaction_amount"))

        if transaction_amount is not None:
            return transaction_amount

        debit_amount = cls._resolved_decimal(resolved_values.get("debit_amount"))
        credit_amount = cls._resolved_decimal(resolved_values.get("credit_amount"))

        if debit_amount is None and credit_amount is None:
            return None

        return (debit_amount or Decimal("0")) - (credit_amount or Decimal("0"))

    @staticmethod
    def _manual_journal_value(
        resolved_values: dict[str, ResolvedFieldValue],
    ) -> str | None:
        """Return the most specific usable manual-journal classification."""

        journal_type = WeekendTransactionsProcedure._resolved_text(
            resolved_values.get("journal_type")
        )

        if journal_type is not None:
            return journal_type

        return WeekendTransactionsProcedure._resolved_text(resolved_values.get("journal_source"))

    @staticmethod
    def _resolved_decimal(
        resolved: ResolvedFieldValue | None,
    ) -> Decimal | None:
        """Return a usable decimal from a resolved audit value."""

        if resolved is None or not resolved.is_usable:
            return None

        value = resolved.value

        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, Decimal):
            return value

        try:
            return Decimal(str(value))
        except InvalidOperation, ValueError:
            return None

    @staticmethod
    def _resolved_text(
        resolved: ResolvedFieldValue | None,
    ) -> str | None:
        """Return normalised usable text from a resolved audit value."""

        if resolved is None or not resolved.is_usable:
            return None

        value = str(resolved.value).strip()

        return value or None

    def _limitations(
        self,
        *,
        context: ProcedureRunContext,
        field_availability: dict[str, bool],
        high_value_threshold: Decimal | None,
        manual_journal_values: frozenset[str],
    ) -> tuple[str, ...]:
        """Return transparent GL-003 execution and analysis limitations."""

        limitations: list[str] = []

        if not context.has_audit_period:
            limitations.append(
                "No audit period was supplied. All usable transaction "
                "dates in the source population were evaluated."
            )

        if not (
            field_availability.get(
                "debit_amount",
                False,
            )
            or field_availability.get(
                "credit_amount",
                False,
            )
        ):
            limitations.append(
                "Debit and credit fields are not mapped; the weekend "
                "debit/credit summary is unavailable."
            )

        if high_value_threshold is None:
            limitations.append(
                "No high-value threshold was supplied; high-value "
                "weekend analysis was not evaluated."
            )
        elif not self._high_value_available(
            threshold=high_value_threshold,
            field_availability=field_availability,
        ):
            limitations.append(
                "A high-value threshold was supplied, but no usable "
                "amount field is mapped; high-value weekend analysis "
                "is unavailable."
            )

        if not manual_journal_values:
            limitations.append(
                "Manual-journal indicator values were not supplied; "
                "manual-journal weekend analysis was not evaluated."
            )
        elif not self._manual_journal_available(
            manual_values=manual_journal_values,
            field_availability=field_availability,
        ):
            limitations.append(
                "Manual-journal indicators were supplied, but neither "
                "Journal Type nor Journal Source is mapped."
            )

        if not self._same_user_available(field_availability):
            limitations.append(
                "Entry User and Approval User are not both mapped; "
                "same-preparer/approver analysis is unavailable."
            )

        return tuple(limitations)

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
