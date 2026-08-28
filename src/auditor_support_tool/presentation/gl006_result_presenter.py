"""GL-006 Segregation of Duties result presentation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
)
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

_MAX_USER_SUMMARY_ROWS = 10


def present_gl006_result(
    result: ProcedureResult,
) -> ResultDashboardPresentation:
    """Build the GL-006 audit-result dashboard model."""

    metrics = result.metrics

    exception_count = result.exception_count
    distinct_users = _as_int(metrics.get("distinct_conflicting_users"))
    highest_count = _as_int(metrics.get("highest_self_approval_count"))
    top_concentration = _as_float(metrics.get("top_user_concentration_pct"))

    journal_available = bool(metrics.get("journal_number_available"))
    account_available = bool(metrics.get("account_code_available"))
    amount_available = bool(metrics.get("transaction_amount_available"))

    affected_journals = _as_int(metrics.get("affected_journals"))
    affected_accounts = _as_int(metrics.get("affected_accounts"))

    user_analysis = _user_analysis_rows(metrics.get("user_self_approval_analysis"))

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
            title="Users with self-approvals",
            value=f"{distinct_users:,}",
            detail="Distinct normalised user identifiers in exceptions",
        ),
        DashboardIndicator(
            title="Highest self-approval count",
            value=f"{highest_count:,}",
            detail="Most exceptions attributed to one user",
        ),
        DashboardIndicator(
            title="Top user concentration",
            value=f"{top_concentration:.1f}%",
            detail="Share of all SoD exceptions attributed to the top user",
        ),
    )

    summary = _user_summary(
        user_analysis=user_analysis,
        journal_available=journal_available,
        amount_available=amount_available,
    )

    observations = _observations(
        result=result,
        distinct_users=distinct_users,
        journal_available=journal_available,
        affected_journals=affected_journals,
        account_available=account_available,
        affected_accounts=affected_accounts,
        user_analysis=user_analysis,
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
        risk_title="Self-Approval Analysis",
        risk_description=(
            "The exception rule compares Entry User and Approval User after "
            "trimming surrounding spaces and ignoring letter case. The user "
            "analysis below ranks the resulting exceptions; it does not add "
            "a separate risk score."
        ),
        risk_indicators=risk_indicators,
        summary=summary,
        observations=observations,
        attention_areas=attention_areas,
        table=table,
        audit_use_statement=result.audit_use_statement,
    )


def _user_summary(
    *,
    user_analysis: tuple[dict[str, object], ...],
    journal_available: bool,
    amount_available: bool,
) -> DashboardSummary:
    """Build the ranked self-approval-by-user summary."""

    visible_rows = user_analysis[:_MAX_USER_SUMMARY_ROWS]
    omitted = max(len(user_analysis) - len(visible_rows), 0)

    description = (
        "Users ranked by number of self-approved transactions. "
        "Percentages use all GL-006 exceptions as the denominator."
    )

    if omitted:
        description += f" Showing the top {_MAX_USER_SUMMARY_ROWS} of {len(user_analysis):,} users."

    rows = tuple(
        DashboardSummaryRow(
            label=str(row.get("user", "")) or "Unknown user",
            values=(
                f"{_as_int(row.get('self_approvals')):,}",
                f"{_as_float(row.get('exception_share_pct')):.1f}%",
                (f"{_as_int(row.get('affected_journals')):,}" if journal_available else "N/A"),
                _amount_summary_value(row) if amount_available else "N/A",
            ),
        )
        for row in visible_rows
    )

    return DashboardSummary(
        title="Self-Approval by User",
        description=description,
        headers=(
            "Self-Approvals",
            "% of Exceptions",
            "Journals",
            "Amount",
        ),
        rows=rows,
    )


def _observations(
    *,
    result: ProcedureResult,
    distinct_users: int,
    journal_available: bool,
    affected_journals: int,
    account_available: bool,
    affected_accounts: int,
    user_analysis: tuple[dict[str, object], ...],
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

    if user_analysis:
        top_user = user_analysis[0]
        top_name = str(top_user.get("user", "")) or "The highest-ranked user"
        top_count = _as_int(top_user.get("self_approvals"))
        top_share = _as_float(top_user.get("exception_share_pct"))

        observations.append(
            f"{top_name} recorded the highest number of self-approvals: "
            f"{top_count:,} of {result.exception_count:,} exceptions "
            f"({top_share:.1f}%)."
        )

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
            "Prioritise users with repeated self-approval exceptions and inspect "
            "the related approval evidence, journals and transaction support."
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


def _amount_summary_value(row: dict[str, object]) -> str:
    """Return the available transaction-amount total for one user row."""

    if _as_int(row.get("transaction_amount_records")) == 0:
        return "N/A"

    value = row.get("transaction_amount_total")

    if isinstance(value, Decimal):
        return f"{value:,.2f}"

    try:
        return f"{Decimal(str(value)):,.2f}"
    except InvalidOperation, ValueError:
        return "N/A"


def _user_analysis_rows(
    value: object,
) -> tuple[dict[str, object], ...]:
    """Return safe procedure-produced user analysis rows."""

    if not isinstance(value, (tuple, list)):
        return ()

    return tuple(row for row in value if isinstance(row, dict))


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


def _as_float(value: object) -> float:
    """Return a float metric with a safe zero fallback."""

    if value is None:
        return 0.0

    try:
        return float(value)
    except TypeError, ValueError:
        return 0.0
