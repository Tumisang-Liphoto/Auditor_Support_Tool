"""GL-006 Segregation of Duties result presentation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
)
from auditor_support_tool.presentation.result_dashboard_models import (
    DashboardIndicator,
    DashboardMetric,
    DashboardTable,
    DashboardTableColumn,
    DashboardTableFilter,
    DashboardTableRow,
    ResultDashboardPresentation,
)


def present_gl006_result(
    result: ProcedureResult,
) -> ResultDashboardPresentation:
    """Build the GL-006 audit-result dashboard model."""

    metrics = result.metrics

    exception_count = result.exception_count
    distinct_users = _as_int(metrics.get("distinct_conflicting_users"))

    journal_available = bool(metrics.get("journal_number_available"))
    account_available = bool(metrics.get("account_code_available"))

    affected_journals = _as_int(metrics.get("affected_journals"))
    affected_accounts = _as_int(metrics.get("affected_accounts"))

    metric_cards = (
        DashboardMetric(
            title="Population",
            value=f"{result.population_count:,}",
            detail="Source records",
            icon_name="fa5s.database",
        ),
        DashboardMetric(
            title="Evaluated",
            value=f"{result.records_evaluated_count:,}",
            detail="Records with both users available",
            icon_name="fa5s.check-circle",
            emphasis="success",
        ),
        DashboardMetric(
            title="SoD Exceptions",
            value=f"{exception_count:,}",
            detail="Same entry and approval user",
            icon_name="fa5s.user-shield",
            emphasis="risk",
        ),
        DashboardMetric(
            title="Exception %",
            value=f"{result.exception_rate:.2f}%",
            detail="Of evaluated records",
            icon_name="fa5s.percentage",
            emphasis="information",
        ),
    )

    risk_indicators = (
        DashboardIndicator(
            title="Distinct conflicting users",
            value=f"{distinct_users:,}",
            detail="Unique normalised user identifiers in exceptions",
        ),
        DashboardIndicator(
            title="Affected journals",
            value=f"{affected_journals:,}" if journal_available else "N/A",
            detail=(
                "Distinct journals containing SoD exceptions"
                if journal_available
                else "Journal Number unavailable"
            ),
            available=journal_available,
        ),
        DashboardIndicator(
            title="Affected accounts",
            value=f"{affected_accounts:,}" if account_available else "N/A",
            detail=(
                "Distinct accounts containing SoD exceptions"
                if account_available
                else "Account Code unavailable"
            ),
            available=account_available,
        ),
    )

    observations = _observations(
        result=result,
        distinct_users=distinct_users,
        journal_available=journal_available,
        affected_journals=affected_journals,
        account_available=account_available,
        affected_accounts=affected_accounts,
    )

    attention_areas = _attention_areas(result=result)

    table = DashboardTable(
        title=(
            f"{exception_count:,} Segregation-of-Duties Exception"
            + ("" if exception_count == 1 else "s")
        ),
        description=(
            "Source-linked records where the normalised entry user and approval user are the same."
        ),
        columns=_table_columns(result.exception_records),
        rows=tuple(_table_row(exception) for exception in result.exception_records),
        filters=(
            DashboardTableFilter(
                key="all",
                label="All Exceptions",
            ),
        ),
        source_note=(
            "Each exception retains its source worksheet row and record "
            "identifier for audit evidence traceability."
        ),
    )

    return ResultDashboardPresentation(
        metrics=metric_cards,
        risk_title="Segregation-of-Duties Analysis",
        risk_description=(
            "The exception rule compares Entry User and Approval User after "
            "trimming surrounding spaces and ignoring letter case."
        ),
        risk_indicators=risk_indicators,
        summary=None,
        observations=observations,
        attention_areas=attention_areas,
        table=table,
        audit_use_statement=result.audit_use_statement,
    )


def _observations(
    *,
    result: ProcedureResult,
    distinct_users: int,
    journal_available: bool,
    affected_journals: int,
    account_available: bool,
    affected_accounts: int,
) -> tuple[str, ...]:
    """Return concise observations grounded in the GL-006 result."""

    observations = [
        (
            f"{result.exception_count:,} record"
            + ("" if result.exception_count == 1 else "s")
            + " were flagged because the same normalised user identifier "
            "appeared as both Entry User and Approval User."
        ),
        (
            f"{distinct_users:,} distinct conflicting user identifier"
            + ("" if distinct_users == 1 else "s")
            + " appeared in the flagged population."
        ),
    ]

    if journal_available:
        observations.append(
            f"The exceptions affected {affected_journals:,} distinct journal"
            + ("" if affected_journals == 1 else "s")
            + "."
        )

    if account_available:
        observations.append(
            f"The exceptions affected {affected_accounts:,} distinct account"
            + ("" if affected_accounts == 1 else "s")
            + "."
        )

    if result.excluded_record_count:
        observations.append(
            f"{result.excluded_record_count:,} source record"
            + ("" if result.excluded_record_count == 1 else "s")
            + " were excluded because one of the required user values was "
            "blank or unusable."
        )

    return tuple(observations)


def _attention_areas(
    *,
    result: ProcedureResult,
) -> tuple[str, ...]:
    """Return appropriate auditor follow-up areas."""

    attention = [
        (
            "Confirm whether the mapped Entry User and Approval User fields "
            "represent distinct workflow responsibilities in the auditee's system."
        ),
        (
            "Inspect approval evidence and workflow configuration for selected "
            "exceptions, especially users appearing repeatedly."
        ),
        (
            "Determine whether any flagged identifiers are system, service, "
            "shared or generic accounts before concluding that self-approval occurred."
        ),
    ]

    if result.excluded_record_count:
        attention.append(
            "Follow up records with missing or unusable user identifiers as a "
            "data-quality or control-evidence issue."
        )

    attention.append(
        "A same-user match is an indicator for audit scrutiny; it does not by "
        "itself establish an improper transaction, control failure, error or fraud."
    )

    return tuple(attention)


def _table_columns(
    exceptions: tuple[ProcedureExceptionRecord, ...],
) -> tuple[DashboardTableColumn, ...]:
    """Return useful GL-006 exception explorer columns."""

    columns: list[DashboardTableColumn] = [
        DashboardTableColumn(
            key="source_row",
            label="Source Row",
        ),
        DashboardTableColumn(
            key="entry_user",
            label="Entry User",
        ),
        DashboardTableColumn(
            key="approval_user",
            label="Approval User",
        ),
    ]

    optional_columns = (
        ("posting_user", "Posting User"),
        ("transaction_id", "Transaction ID"),
        ("journal_number", "Journal"),
        ("transaction_date", "Transaction Date"),
        ("posting_date", "Posting Date"),
        ("transaction_amount", "Amount"),
        ("account_code", "Account"),
        ("transaction_description", "Description"),
        ("approval_date", "Approval Date"),
        ("approval_timestamp", "Approval Timestamp"),
    )

    for key, label in optional_columns:
        if any(key in exception.values for exception in exceptions):
            columns.append(
                DashboardTableColumn(
                    key=key,
                    label=label,
                )
            )

    return tuple(columns)


def _table_row(
    exception: ProcedureExceptionRecord,
) -> DashboardTableRow:
    """Convert one GL-006 exception to a dashboard row."""

    values: dict[str, str] = {
        "source_row": str(exception.source_row_number),
        "record_id": exception.source_record_id,
        "reason": exception.reason,
    }

    for key, raw_value in exception.values.items():
        if key == "normalised_user":
            continue

        values[key] = _display_value(raw_value)

    return DashboardTableRow(values=values)


def _display_value(value: object) -> str:
    """Return a compact display value for a dashboard table cell."""

    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Decimal):
        return f"{value:,.2f}"

    if value is None:
        return "—"

    text = str(value).strip()

    return text or "—"


def _as_int(value: object) -> int:
    """Return an integer metric with a safe zero fallback."""

    if value is None:
        return 0

    try:
        return int(value)
    except TypeError, ValueError:
        return 0
