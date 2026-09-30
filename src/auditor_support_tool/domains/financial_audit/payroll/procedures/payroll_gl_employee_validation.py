"""PAY001: validate payroll-related GL employee identifiers against Employee Master."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from auditor_support_tool.core.audit_execution_models import ExecutionCancellationToken
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import AuditRecord, AuditRecordSource
from auditor_support_tool.core.prepared_audit_dataset import ResolvedFieldValue
from auditor_support_tool.core.procedure_dataset_resolution import ProcedureDatasetBundle
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.domains.financial_audit.payroll.procedure_catalogue import (
    PAY001_DEFINITION,
)

_NOT_FOUND = "employee_not_found_in_master"
_NOT_ACTIVE = "employee_not_active"


@dataclass(frozen=True, slots=True)
class _EmployeeReference:
    employee_name: object | None
    employment_status: object | None
    department: object | None


class PayrollGlEmployeeValidationProcedure:
    """Apply PAY001's deterministic employee-master comparison."""

    @property
    def definition(self) -> ProcedureDefinition:
        return PAY001_DEFINITION

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
                "PAY001 requires resolved General Ledger and Employee Master datasets."
            )

        ledger = source.require_source("general_ledger")
        employee_master = source.require_source("employee_master")
        references: dict[str, list[_EmployeeReference]] = {}
        blank_reference_identifiers = 0

        for record in employee_master.iter_records():
            cancellation_token.raise_if_cancelled()
            key = _identifier_key(record.resolve("employee_id"))
            if not key:
                blank_reference_identifiers += 1
                continue
            references.setdefault(key, []).append(_reference(record))

        ambiguous_keys = {key for key, records in references.items() if len(records) > 1}
        usable_reference_records = sum(len(records) for records in references.values())
        duplicate_reference_records = sum(
            len(records) - 1 for records in references.values() if len(records) > 1
        )

        configured = context.parameters.get("payroll_descriptions")
        if not isinstance(configured, (list, tuple)) or not configured:
            raise ValueError("PAY001 requires at least one configured payroll description.")
        payroll_descriptions = {key for value in configured if (key := _comparison_text(value))}
        if not payroll_descriptions:
            raise ValueError("PAY001 requires at least one usable payroll description.")

        exceptions: list[ProcedureExceptionRecord] = []
        exclusions: Counter[str] = Counter()
        observations: Counter[str] = Counter()
        status_distribution: Counter[str] = Counter()
        non_active_employee_keys: set[str] = set()
        payroll_population = 0
        evaluated = 0
        unmatched = 0

        for record in ledger.iter_records():
            cancellation_token.raise_if_cancelled()
            description = _comparison_text(record.resolve("transaction_description"))
            if description not in payroll_descriptions:
                continue

            payroll_population += 1
            employee_number = record.resolve("employee_number")
            employee_key = _identifier_key(employee_number)
            if not employee_key:
                exclusions["blank_employee_number"] += 1
                observations["blank_employee_number"] += 1
                continue

            matches = references.get(employee_key)
            if matches is None:
                evaluated += 1
                unmatched += 1
                exceptions.append(
                    _exception(
                        record,
                        employee_number=employee_number,
                        reason_code=_NOT_FOUND,
                        reason=(
                            "Payroll-related GL posting contains an employee identifier that "
                            "could not be matched to the supplied Employee Master."
                        ),
                    )
                )
                continue

            if employee_key in ambiguous_keys:
                exclusions["ambiguous_employee_master_identifier"] += 1
                observations["ambiguous_employee_master_identifier"] += 1
                continue

            reference = matches[0]
            status_key = _comparison_text(reference.employment_status)
            if not status_key:
                exclusions["missing_employee_status"] += 1
                observations["missing_employee_status"] += 1
                continue

            evaluated += 1
            if status_key == "active":
                continue

            non_active_employee_keys.add(employee_key)
            status_label = str(reference.employment_status).strip()
            status_distribution[status_label] += 1
            exceptions.append(
                _exception(
                    record,
                    employee_number=employee_number,
                    reason_code=_NOT_ACTIVE,
                    reason=(
                        "Payroll-related GL posting is associated with an employee whose "
                        "Employment Status in the supplied Employee Master is not Active."
                    ),
                    reference=reference,
                )
            )

        if blank_reference_identifiers:
            observations["blank_employee_master_identifier"] = blank_reference_identifiers
        if ambiguous_keys:
            observations["duplicate_employee_master_identifier"] = len(ambiguous_keys)

        return ProcedureResult.create(
            context=context,
            population_count=payroll_population,
            records_evaluated_count=evaluated,
            exception_records=tuple(exceptions),
            exclusion_counts=dict(exclusions),
            data_quality_observation_counts=dict(observations),
            limitations=self.definition.limitations,
            metrics={
                "total_gl_records_scanned": ledger.record_count,
                "payroll_related_population": payroll_population,
                "blank_employee_number_count": exclusions["blank_employee_number"],
                "unmatched_employee_record_count": unmatched,
                "non_active_employee_record_count": sum(status_distribution.values()),
                "unique_non_active_employee_count": len(non_active_employee_keys),
                "reference_employee_master_record_count": employee_master.record_count,
                "usable_reference_employee_identifier_count": usable_reference_records,
                "blank_reference_employee_identifier_count": blank_reference_identifiers,
                "ambiguous_reference_employee_identifier_count": len(ambiguous_keys),
                "duplicate_reference_employee_record_count": duplicate_reference_records,
                "exception_current_status_distribution": dict(sorted(status_distribution.items())),
                "reference_dataset_id": employee_master.dataset_id,
            },
        )


def _comparison_text(value: object | ResolvedFieldValue | None) -> str:
    if isinstance(value, ResolvedFieldValue):
        if not value.is_usable:
            return ""
        value = value.value
    if value is None:
        return ""
    return str(value).strip().casefold()


def _identifier_key(value: ResolvedFieldValue) -> str:
    """Compare values interpreted by the shared identifier-semantics boundary."""

    return _comparison_text(value)


def _reference(record: AuditRecord) -> _EmployeeReference:
    department = record.resolve("department_name")
    if not department.is_usable:
        department = record.resolve("department_code")
    return _EmployeeReference(
        employee_name=_evidence_value(record.resolve("employee_name")),
        employment_status=_evidence_value(record.resolve("employment_status")),
        department=_evidence_value(department),
    )


def _exception(
    record: AuditRecord,
    *,
    employee_number: ResolvedFieldValue,
    reason_code: str,
    reason: str,
    reference: _EmployeeReference | None = None,
) -> ProcedureExceptionRecord:
    values: dict[str, object] = {}
    for key in (
        "transaction_date",
        "journal_number",
        "transaction_description",
        "employee_number",
        "account_code",
        "debit_amount",
        "credit_amount",
        "transaction_amount",
        "cost_centre_code",
    ):
        value = _evidence_value(record.resolve(key))
        if value is not None:
            values[key] = value

    values["employee_number"] = _evidence_value(employee_number)
    if reference is not None:
        if reference.employee_name is not None:
            values["employee_name"] = reference.employee_name
        if reference.employment_status is not None:
            values["employment_status"] = reference.employment_status
        if reference.department is not None:
            values["department"] = reference.department
    values["exception_reason"] = reason_code

    return ProcedureExceptionRecord.create(
        source_record_id=record.source_record_id,
        source_row_number=record.source_row_number,
        reason_code=reason_code,
        reason=reason,
        values=values,
    )


def _evidence_value(value: ResolvedFieldValue) -> object | None:
    if not value.is_usable:
        return None
    return value.raw_value
