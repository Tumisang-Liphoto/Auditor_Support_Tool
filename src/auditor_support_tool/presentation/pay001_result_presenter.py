"""PAY001 payroll GL employee-validation result presentation."""

from auditor_support_tool.core.audit_procedure_models import ProcedureResult
from auditor_support_tool.core.currency import format_monetary_value, is_monetary_field
from auditor_support_tool.presentation.result_dashboard_models import (
    DashboardIndicator,
    DashboardMetric,
    DashboardSummary,
    DashboardSummaryRow,
    DashboardTable,
    DashboardTableColumn,
    DashboardTableFilter,
    DashboardTableRow,
    ResultDashboardPresentation,
)

_COLUMN_LABELS = {
    "source_row": "Source Row",
    "exception_reason": "Exception Reason",
    "transaction_date": "Transaction Date",
    "journal_number": "Journal Number",
    "transaction_description": "Description",
    "employee_number": "Employee Number",
    "account_code": "Account Code",
    "debit_amount": "Debit Amount",
    "credit_amount": "Credit Amount",
    "transaction_amount": "Net / Transaction Amount",
    "cost_centre_code": "Cost Centre",
    "employee_name": "Employee Name",
    "employment_status": "Current Employment Status",
    "department": "Department",
    "record_id": "Source Record ID",
}


def present_pay001_result(result: ProcedureResult) -> ResultDashboardPresentation:
    """Build a PAY001 dashboard without changing deterministic membership."""

    metrics = result.metrics
    status_distribution = metrics.get("exception_current_status_distribution", {})
    if not isinstance(status_distribution, dict):
        status_distribution = {}

    observations = [
        (
            f"{result.population_count:,} of "
            f"{_as_int(metrics.get('total_gl_records_scanned')):,} scanned General Ledger "
            "records matched the configured payroll descriptions."
        ),
        (
            f"{result.exception_count:,} evaluated payroll record"
            + ("" if result.exception_count == 1 else "s")
            + " require auditor review."
        ),
    ]
    if result.excluded_record_count:
        observations.append(
            f"{result.excluded_record_count:,} payroll-related record"
            + (" was" if result.excluded_record_count == 1 else "s were")
            + " excluded from employee-status evaluation; exclusion reasons are data-quality "
            "conditions and are not exceptions."
        )
    for reason, count in result.data_quality_observation_counts.items():
        observations.append(f"Data-quality observation — {reason}: {count:,}.")
    observations.extend(result.limitations)

    keys = ["source_row", "exception_reason"]
    for key in _COLUMN_LABELS:
        if key in {"source_row", "exception_reason", "record_id"}:
            continue
        if any(key in exception.values for exception in result.exception_records):
            keys.append(key)
    keys.append("record_id")

    rows = tuple(
        DashboardTableRow(
            values={
                "source_row": str(exception.source_row_number),
                **{
                    key: _format(key, exception.values.get(key), result.context.audit_currency)
                    for key in keys
                    if key not in {"source_row", "record_id"}
                },
                "record_id": exception.source_record_id,
            },
            groups=frozenset({"all", exception.reason_code}),
        )
        for exception in result.exception_records
    )

    return ResultDashboardPresentation(
        metrics=(
            DashboardMetric(
                title="Payroll Population",
                value=f"{result.population_count:,}",
                detail="GL records matching configured descriptions",
                icon_name="fa5s.database",
            ),
            DashboardMetric(
                title="Evaluated",
                value=f"{result.records_evaluated_count:,}",
                detail="Records evaluated against Employee Master",
                icon_name="fa5s.check-circle",
                emphasis="information",
            ),
            DashboardMetric(
                title="Exceptions",
                value=f"{result.exception_count:,}",
                detail="Records requiring auditor review",
                icon_name="fa5s.exclamation-triangle",
                emphasis="risk",
            ),
            DashboardMetric(
                title="Excluded",
                value=f"{result.excluded_record_count:,}",
                detail="Data-quality conditions, not exceptions",
                icon_name="fa5s.info-circle",
            ),
        ),
        risk_title="Deterministic Employee Validation",
        risk_description=(
            "Exceptions are unmatched usable identifiers or matched employees whose current "
            "master-file status is not Active."
        ),
        risk_indicators=(
            DashboardIndicator(
                title="Unmatched employee records",
                value=f"{_as_int(metrics.get('unmatched_employee_record_count')):,}",
                detail="Usable GL identifiers absent from Employee Master",
            ),
            DashboardIndicator(
                title="Non-Active employee records",
                value=f"{_as_int(metrics.get('non_active_employee_record_count')):,}",
                detail="Matched records with current status other than Active",
            ),
            DashboardIndicator(
                title="Unique non-Active employees",
                value=f"{_as_int(metrics.get('unique_non_active_employee_count')):,}",
                detail="Distinct matched employee identifiers in exceptions",
            ),
        ),
        summary=DashboardSummary(
            title="Current Status of Exception Employees",
            description=(
                "Current Employee Master status only; effective-date conclusions are not made."
            ),
            headers=("Exception Records",),
            rows=tuple(
                DashboardSummaryRow(label=str(status), values=(f"{_as_int(count):,}",))
                for status, count in status_distribution.items()
            ),
        ),
        observations=tuple(observations),
        attention_areas=(
            "Investigate source support and Employee Master completeness before drawing a finding.",
            result.audit_use_statement,
        ),
        table=DashboardTable(
            title=f"{result.exception_count:,} PAY001 Exception"
            + ("" if result.exception_count == 1 else "s"),
            description="Source-linked payroll GL records selected by PAY001.",
            columns=tuple(DashboardTableColumn(key=key, label=_COLUMN_LABELS[key]) for key in keys),
            rows=rows,
            filters=(
                DashboardTableFilter(key="all", label="All Exceptions"),
                DashboardTableFilter(
                    key="employee_not_found_in_master", label="Not in Employee Master"
                ),
                DashboardTableFilter(key="employee_not_active", label="Current Status Not Active"),
            ),
            source_note=(
                "Each exception retains its General Ledger source row and record identifier; "
                "Employee Master fields are supporting reference evidence."
            ),
        ),
        audit_use_statement=result.audit_use_statement,
    )


def _format(key: str, value: object, currency: str) -> str:
    if value is None:
        return "—"
    if is_monetary_field(key) and currency.strip():
        return format_monetary_value(value, currency)
    return str(value)


def _as_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
