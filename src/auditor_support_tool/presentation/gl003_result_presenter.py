"""GL-003 Weekend Transactions result presentation."""

from __future__ import annotations

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


def present_gl003_result(
    result: ProcedureResult,
) -> ResultDashboardPresentation:
    """Build the GL-003 audit-result dashboard model."""

    metrics = result.metrics

    saturday = _as_int(metrics.get("saturday_transactions"))
    sunday = _as_int(metrics.get("sunday_transactions"))
    weekend_percentage = _as_decimal(metrics.get("weekend_percentage"))

    high_risk_available = bool(metrics.get("high_risk_available"))
    high_risk_count = _as_int(metrics.get("high_risk_weekend_count"))

    evaluated_indicators = _as_text_tuple(metrics.get("evaluated_risk_indicators"))
    unavailable_indicators = _as_text_tuple(metrics.get("unavailable_risk_indicators"))

    metric_cards = (
        DashboardMetric(
            title="Saturday",
            value=f"{saturday:,}",
            detail="Weekend transactions",
            icon_name="fa5s.calendar-day",
            emphasis="information",
        ),
        DashboardMetric(
            title="Sunday",
            value=f"{sunday:,}",
            detail="Weekend transactions",
            icon_name="fa5s.calendar-day",
            emphasis="information",
        ),
        DashboardMetric(
            title="Weekend %",
            value=_format_percentage(weekend_percentage),
            detail="Of evaluated records",
            icon_name="fa5s.percentage",
            emphasis="information",
        ),
        DashboardMetric(
            title="High Risk",
            value=(f"{high_risk_count:,}" if high_risk_available else "N/A"),
            detail=(
                f"Based on {len(evaluated_indicators)} of 3 additional indicators"
                if high_risk_available
                else "Additional indicators unavailable"
            ),
            icon_name="fa5s.exclamation-triangle",
            emphasis=("risk" if high_risk_available else "muted"),
        ),
    )

    risk_indicators = (
        _high_value_indicator(metrics),
        _manual_journal_indicator(metrics),
        _same_user_indicator(metrics),
    )

    risk_description = f"{len(evaluated_indicators)} of 3 additional indicators were evaluated."

    if unavailable_indicators:
        risk_description += " N/A means the required mapping or audit rule was unavailable."

    summary = _build_debit_credit_summary(metrics)

    observations = _build_observations(
        result=result,
        saturday=saturday,
        sunday=sunday,
        weekend_percentage=weekend_percentage,
        high_risk_available=high_risk_available,
        high_risk_count=high_risk_count,
        evaluated_indicator_count=len(evaluated_indicators),
    )

    attention_areas = _build_attention_areas(
        result=result,
        metrics=metrics,
    )

    table = DashboardTable(
        title=(
            f"{result.exception_count:,} Weekend Transaction"
            + ("" if result.exception_count == 1 else "s")
        ),
        description=("Source-linked weekend transactions identified for auditor review."),
        columns=_table_columns(result.exception_records),
        rows=tuple(_table_row(exception) for exception in result.exception_records),
        filters=(
            DashboardTableFilter(
                key="all",
                label="All Transactions",
            ),
            DashboardTableFilter(
                key="high_risk",
                label="High Risk Only",
            ),
            DashboardTableFilter(
                key="saturday",
                label="Saturday Only",
            ),
            DashboardTableFilter(
                key="sunday",
                label="Sunday Only",
            ),
        ),
        source_note=(
            "Each row retains its source worksheet row and "
            "record identifier for audit evidence traceability."
        ),
    )

    return ResultDashboardPresentation(
        metrics=metric_cards,
        risk_title="Risk Indicators",
        risk_description=risk_description,
        risk_indicators=risk_indicators,
        summary=summary,
        observations=observations,
        attention_areas=attention_areas,
        table=table,
        audit_use_statement=result.audit_use_statement,
    )


def _high_value_indicator(
    metrics: dict[str, object],
) -> DashboardIndicator:
    available = bool(metrics.get("high_value_available"))
    threshold = _as_decimal(metrics.get("high_value_threshold"))

    if not available:
        if threshold is None:
            detail = "High-value threshold not configured"
        else:
            detail = "Usable amount field unavailable"

        return DashboardIndicator(
            title="High-value weekend transactions",
            value="N/A",
            detail=detail,
            available=False,
        )

    return DashboardIndicator(
        title="High-value weekend transactions",
        value=f"{_as_int(metrics.get('high_value_weekend_count')):,}",
        detail=(f"Threshold ≥ {_format_number(threshold)}"),
    )


def _manual_journal_indicator(
    metrics: dict[str, object],
) -> DashboardIndicator:
    available = bool(metrics.get("manual_journal_available"))

    if not available:
        configured_values = _as_text_tuple(metrics.get("manual_journal_values"))

        detail = (
            "Manual-journal values not configured"
            if not configured_values
            else "Journal Type/Source unavailable"
        )

        return DashboardIndicator(
            title="Manual journals on weekends",
            value="N/A",
            detail=detail,
            available=False,
        )

    return DashboardIndicator(
        title="Manual journals on weekends",
        value=f"{_as_int(metrics.get('manual_journal_weekend_count')):,}",
        detail="Matched configured manual-journal values",
    )


def _same_user_indicator(
    metrics: dict[str, object],
) -> DashboardIndicator:
    available = bool(metrics.get("same_preparer_approver_available"))

    if not available:
        return DashboardIndicator(
            title="Same preparer and approver",
            value="N/A",
            detail="Entry User and Approval User required",
            available=False,
        )

    return DashboardIndicator(
        title="Same preparer and approver",
        value=f"{_as_int(metrics.get('same_preparer_approver_count')):,}",
        detail="Normalised nonblank user values matched",
    )


def _build_debit_credit_summary(
    metrics: dict[str, object],
) -> DashboardSummary:
    debit_available = bool(metrics.get("debit_summary_available"))
    credit_available = bool(metrics.get("credit_summary_available"))

    return DashboardSummary(
        title="Weekend Credit & Debit Summary",
        description=("Amounts represented by the identified weekend transactions."),
        headers=(
            "Debit",
            "Credit",
        ),
        rows=(
            DashboardSummaryRow(
                label="Saturday",
                values=(
                    _summary_amount(
                        metrics.get("saturday_debit_total"),
                        available=debit_available,
                    ),
                    _summary_amount(
                        metrics.get("saturday_credit_total"),
                        available=credit_available,
                    ),
                ),
            ),
            DashboardSummaryRow(
                label="Sunday",
                values=(
                    _summary_amount(
                        metrics.get("sunday_debit_total"),
                        available=debit_available,
                    ),
                    _summary_amount(
                        metrics.get("sunday_credit_total"),
                        available=credit_available,
                    ),
                ),
            ),
            DashboardSummaryRow(
                label="Total",
                values=(
                    _summary_amount(
                        metrics.get("weekend_debit_total"),
                        available=debit_available,
                    ),
                    _summary_amount(
                        metrics.get("weekend_credit_total"),
                        available=credit_available,
                    ),
                ),
            ),
        ),
    )


def _build_observations(
    *,
    result: ProcedureResult,
    saturday: int,
    sunday: int,
    weekend_percentage: Decimal | None,
    high_risk_available: bool,
    high_risk_count: int,
    evaluated_indicator_count: int,
) -> tuple[str, ...]:
    observations = [
        (
            f"{result.exception_count:,} weekend transactions "
            f"were identified, representing "
            f"{_format_percentage(weekend_percentage)} of "
            f"{result.records_evaluated_count:,} evaluated records."
        ),
        (
            f"Saturday activity accounted for {saturday:,} "
            f"records and Sunday activity for {sunday:,}."
        ),
    ]

    if high_risk_available:
        observations.append(
            f"{high_risk_count:,} unique weekend transactions "
            "matched at least one of the "
            f"{evaluated_indicator_count} additional risk "
            "indicators evaluated."
        )
    else:
        observations.append(
            "Additional risk overlays were not available for "
            "this run; review the disclosed limitations before "
            "drawing conclusions."
        )

    if result.excluded_record_count:
        observations.append(
            f"{result.excluded_record_count:,} source records "
            "were excluded from evaluation under the "
            "procedure's recorded exclusion rules."
        )

    return tuple(observations)


def _build_attention_areas(
    *,
    result: ProcedureResult,
    metrics: dict[str, object],
) -> tuple[str, ...]:
    attention: list[str] = []

    if bool(metrics.get("high_value_available")) and _as_int(
        metrics.get("high_value_weekend_count")
    ):
        attention.append(
            "Prioritise high-value weekend transactions for "
            "supporting-document and business-purpose review."
        )

    if bool(metrics.get("manual_journal_available")) and _as_int(
        metrics.get("manual_journal_weekend_count")
    ):
        attention.append(
            "Inspect weekend manual journals for evidence of "
            "appropriate authorisation and supporting rationale."
        )

    if bool(metrics.get("same_preparer_approver_available")) and _as_int(
        metrics.get("same_preparer_approver_count")
    ):
        attention.append(
            "Review same-user preparation and approval for "
            "valid segregation-of-duties exceptions or "
            "authorised overrides."
        )

    if not attention:
        attention.append(
            "Review the weekend transactions together with the "
            "recorded limitations and available supporting "
            "fields to determine appropriate follow-up."
        )

    if result.limitations:
        attention.append(
            "Some analytical overlays were unavailable or "
            "limited. Treat N/A indicators as not evaluated, "
            "not as zero exceptions."
        )

    attention.append(
        "Weekend timing and additional indicators identify "
        "records for scrutiny; they do not by themselves "
        "establish an audit finding."
    )

    return tuple(attention)


def _table_columns(
    exceptions: tuple[
        ProcedureExceptionRecord,
        ...,
    ],
) -> tuple[DashboardTableColumn, ...]:
    columns: list[DashboardTableColumn] = [
        DashboardTableColumn(
            key="source_row",
            label="Source Row",
        ),
        DashboardTableColumn(
            key="transaction_date",
            label="Date",
        ),
        DashboardTableColumn(
            key="day_of_week",
            label="Day",
        ),
    ]

    optional_columns = (
        (
            "journal_number",
            "Journal",
        ),
        (
            "account_code",
            "Account",
        ),
        (
            "transaction_description",
            "Description",
        ),
        (
            "debit_amount",
            "Debit",
        ),
        (
            "credit_amount",
            "Credit",
        ),
        (
            "transaction_amount",
            "Amount",
        ),
        (
            "entry_user",
            "Prepared By",
        ),
        (
            "approval_user",
            "Approved By",
        ),
        (
            "journal_type",
            "Journal Type",
        ),
        (
            "journal_source",
            "Source",
        ),
    )

    for key, label in optional_columns:
        if any(key in exception.values for exception in exceptions):
            columns.append(
                DashboardTableColumn(
                    key=key,
                    label=label,
                )
            )

    columns.append(
        DashboardTableColumn(
            key="risk_indicators",
            label="Risk Indicators",
        )
    )

    return tuple(columns)


def _table_row(
    exception: ProcedureExceptionRecord,
) -> DashboardTableRow:
    values: dict[str, str] = {
        "source_row": str(exception.source_row_number),
        "record_id": exception.source_record_id,
        "reason": exception.reason,
    }

    for key, raw_value in exception.values.items():
        values[key] = _display_value(
            key,
            raw_value,
        )

    day_name = values.get(
        "day_of_week",
        "",
    ).casefold()

    groups = {
        "all",
    }

    if day_name == "saturday":
        groups.add("saturday")
    elif day_name == "sunday":
        groups.add("sunday")

    if bool(exception.values.get("high_risk")):
        groups.add("high_risk")

    return DashboardTableRow(
        values=values,
        groups=frozenset(groups),
    )


def _display_value(
    key: str,
    value: object,
) -> str:
    if key == "risk_indicators":
        indicators = _as_text_tuple(value)

        if not indicators:
            return "—"

        labels = {
            "high_value": "High value",
            "manual_journal": "Manual journal",
            "same_preparer_approver": "Same user",
        }

        return ", ".join(
            labels.get(
                indicator,
                indicator.replace("_", " ").title(),
            )
            for indicator in indicators
        )

    if isinstance(value, Decimal):
        return _format_number(value)

    if value is None:
        return "—"

    text = str(value).strip()

    return text or "—"


def _summary_amount(
    value: object,
    *,
    available: bool,
) -> str:
    if not available:
        return "N/A"

    return _format_number(_as_decimal(value))


def _format_percentage(
    value: Decimal | None,
) -> str:
    if value is None:
        return "0.0%"

    return f"{value:.1f}%"


def _format_number(
    value: Decimal | None,
) -> str:
    if value is None:
        return "0.00"

    return f"{value:,.2f}"


def _as_int(
    value: object,
) -> int:
    if value is None:
        return 0

    try:
        return int(value)
    except TypeError, ValueError:
        return 0


def _as_decimal(
    value: object,
) -> Decimal | None:
    if value is None or isinstance(
        value,
        bool,
    ):
        return None

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):
        return None


def _as_text_tuple(
    value: object,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        text = value.strip()

        return (text,) if text else ()

    if isinstance(
        value,
        (tuple, list, set, frozenset),
    ):
        return tuple(str(item).strip() for item in value if str(item).strip())

    return ()
