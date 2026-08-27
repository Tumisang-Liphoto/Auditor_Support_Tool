"""GL-001 Duplicate Invoice Detection result presentation."""

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
    DashboardSummary,
    DashboardSummaryRow,
    DashboardTable,
    DashboardTableColumn,
    DashboardTableFilter,
    DashboardTableRow,
    ResultDashboardPresentation,
)


def present_gl001_result(
    result: ProcedureResult,
) -> ResultDashboardPresentation:
    """Build the GL-001 audit-result dashboard model."""

    metrics = result.metrics

    duplicate_groups = _as_int(metrics.get("duplicate_groups"))
    flagged_records = _as_int(metrics.get("flagged_records"))
    additional_duplicates = _as_int(metrics.get("additional_duplicate_records"))

    vendor_analysis_available = bool(metrics.get("vendor_analysis_available"))
    same_vendor_groups = _as_int(metrics.get("same_vendor_groups"))
    multiple_vendor_groups = _as_int(metrics.get("multiple_vendor_groups"))
    not_assessable_groups = _as_int(metrics.get("vendor_not_assessable_groups"))

    metric_cards = (
        DashboardMetric(
            title="Population",
            value=f"{result.population_count:,}",
            detail="Source records",
            icon_name="fa5s.database",
        ),
        DashboardMetric(
            title="Tested",
            value=f"{result.records_evaluated_count:,}",
            detail="Nonblank usable invoice numbers",
            icon_name="fa5s.check-circle",
            emphasis="success",
        ),
        DashboardMetric(
            title="Duplicate Groups",
            value=f"{duplicate_groups:,}",
            detail="Repeated invoice numbers",
            icon_name="fa5s.copy",
            emphasis="information",
        ),
        DashboardMetric(
            title="Records Flagged",
            value=f"{flagged_records:,}",
            detail="All records in duplicate groups",
            icon_name="fa5s.exclamation-triangle",
            emphasis="risk",
        ),
    )

    risk_indicators = (
        DashboardIndicator(
            title="Additional duplicate records",
            value=f"{additional_duplicates:,}",
            detail="Records beyond the first occurrence in each group",
        ),
        DashboardIndicator(
            title="Same-vendor groups",
            value=(f"{same_vendor_groups:,}" if vendor_analysis_available else "N/A"),
            detail=(
                "Repeated invoice number within one assessable vendor"
                if vendor_analysis_available
                else "Vendor Code/Name unavailable"
            ),
            available=vendor_analysis_available,
        ),
        DashboardIndicator(
            title="Multiple-vendor groups",
            value=(f"{multiple_vendor_groups:,}" if vendor_analysis_available else "N/A"),
            detail=(
                "Same invoice number appears across different vendors"
                if vendor_analysis_available
                else "Vendor Code/Name unavailable"
            ),
            available=vendor_analysis_available,
        ),
    )

    summary = _vendor_summary(
        metrics=metrics,
        vendor_analysis_available=vendor_analysis_available,
    )

    observations = _observations(
        result=result,
        duplicate_groups=duplicate_groups,
        flagged_records=flagged_records,
        additional_duplicates=additional_duplicates,
        vendor_analysis_available=vendor_analysis_available,
        same_vendor_groups=same_vendor_groups,
        multiple_vendor_groups=multiple_vendor_groups,
        not_assessable_groups=not_assessable_groups,
    )

    attention_areas = _attention_areas(
        result=result,
        metrics=metrics,
        vendor_analysis_available=vendor_analysis_available,
    )

    table = DashboardTable(
        title=(
            f"{result.exception_count:,} Duplicate Invoice Record"
            + ("" if result.exception_count == 1 else "s")
        ),
        description=("All source-linked records belonging to repeated invoice-number groups."),
        columns=_table_columns(result.exception_records),
        rows=tuple(_table_row(exception) for exception in result.exception_records),
        filters=(
            DashboardTableFilter(
                key="all",
                label="All Duplicates",
            ),
            DashboardTableFilter(
                key="same_vendor",
                label="Same Vendor",
            ),
            DashboardTableFilter(
                key="multiple_vendors",
                label="Multiple Vendors",
            ),
            DashboardTableFilter(
                key="not_assessable",
                label="Vendor N/A",
            ),
            DashboardTableFilter(
                key="three_plus",
                label="3+ Records",
            ),
        ),
        source_note=(
            "Each flagged row retains its source worksheet row and "
            "record identifier for audit evidence traceability."
        ),
    )

    return ResultDashboardPresentation(
        metrics=metric_cards,
        risk_title="Duplicate Pattern Analysis",
        risk_description=(
            "Repeated invoice numbers are the exception rule. "
            "Vendor information is supporting context and does not "
            "change whether a record is flagged."
        ),
        risk_indicators=risk_indicators,
        summary=summary,
        observations=observations,
        attention_areas=attention_areas,
        table=table,
        audit_use_statement=result.audit_use_statement,
    )


def _vendor_summary(
    *,
    metrics: dict[str, object],
    vendor_analysis_available: bool,
) -> DashboardSummary:
    """Build the duplicate-group vendor relationship summary."""

    if not vendor_analysis_available:
        return DashboardSummary(
            title="Vendor Relationship Summary",
            description=(
                "Vendor context is unavailable because Vendor Code and Vendor Name are not mapped."
            ),
            headers=(
                "Groups",
                "Flagged Records",
            ),
            rows=(
                DashboardSummaryRow(
                    label="Not assessable",
                    values=(
                        f"{_as_int(metrics.get('vendor_not_assessable_groups')):,}",
                        f"{_as_int(metrics.get('vendor_not_assessable_records')):,}",
                    ),
                ),
            ),
        )

    return DashboardSummary(
        title="Vendor Relationship Summary",
        description=("Supporting context for the repeated invoice-number groups."),
        headers=(
            "Groups",
            "Flagged Records",
        ),
        rows=(
            DashboardSummaryRow(
                label="Same vendor",
                values=(
                    f"{_as_int(metrics.get('same_vendor_groups')):,}",
                    f"{_as_int(metrics.get('same_vendor_records')):,}",
                ),
            ),
            DashboardSummaryRow(
                label="Multiple vendors",
                values=(
                    f"{_as_int(metrics.get('multiple_vendor_groups')):,}",
                    f"{_as_int(metrics.get('multiple_vendor_records')):,}",
                ),
            ),
            DashboardSummaryRow(
                label="Not assessable",
                values=(
                    f"{_as_int(metrics.get('vendor_not_assessable_groups')):,}",
                    f"{_as_int(metrics.get('vendor_not_assessable_records')):,}",
                ),
            ),
        ),
    )


def _observations(
    *,
    result: ProcedureResult,
    duplicate_groups: int,
    flagged_records: int,
    additional_duplicates: int,
    vendor_analysis_available: bool,
    same_vendor_groups: int,
    multiple_vendor_groups: int,
    not_assessable_groups: int,
) -> tuple[str, ...]:
    """Return concise observations grounded in the GL-001 result."""

    observations = [
        (
            f"{duplicate_groups:,} repeated invoice-number group"
            + ("" if duplicate_groups == 1 else "s")
            + f" contained {flagged_records:,} flagged record"
            + ("" if flagged_records == 1 else "s")
            + f" from {result.records_evaluated_count:,} evaluated records."
        ),
        (
            f"{additional_duplicates:,} record"
            + ("" if additional_duplicates == 1 else "s")
            + " occurred beyond the first occurrence in the "
            "identified duplicate groups."
        ),
    ]

    if vendor_analysis_available:
        observations.append(
            f"{same_vendor_groups:,} duplicate group"
            + ("" if same_vendor_groups == 1 else "s")
            + " related to one assessable vendor, while "
            f"{multiple_vendor_groups:,} group"
            + ("" if multiple_vendor_groups == 1 else "s")
            + " contained records across multiple vendors."
        )

        if not_assessable_groups:
            observations.append(
                f"Vendor relationship could not be assessed for "
                f"{not_assessable_groups:,} duplicate group"
                + ("" if not_assessable_groups == 1 else "s")
                + " because complete usable vendor values were unavailable."
            )
    else:
        observations.append("Vendor relationship analysis was not available for this run.")

    if result.excluded_record_count:
        observations.append(
            f"{result.excluded_record_count:,} source record"
            + ("" if result.excluded_record_count == 1 else "s")
            + " were excluded because the invoice number was blank "
            "or unusable."
        )

    return tuple(observations)


def _attention_areas(
    *,
    result: ProcedureResult,
    metrics: dict[str, object],
    vendor_analysis_available: bool,
) -> tuple[str, ...]:
    """Return appropriate auditor follow-up areas."""

    attention: list[str] = []

    if vendor_analysis_available and _as_int(metrics.get("same_vendor_groups")):
        attention.append(
            "Prioritise same-vendor duplicate groups for invoice, "
            "payment and posting support to determine whether the "
            "repetition represents a valid split, reversal, partial "
            "payment or another legitimate circumstance."
        )

    if vendor_analysis_available and _as_int(metrics.get("multiple_vendor_groups")):
        attention.append(
            "Review multiple-vendor groups carefully because unrelated "
            "suppliers may legitimately use the same invoice numbering."
        )

    if _as_int(metrics.get("blank_invoice_number_count")):
        attention.append(
            "Follow up blank invoice-number records as a data-quality "
            "matter because they were not evaluated by this procedure."
        )

    if not attention:
        attention.append(
            "Review the flagged duplicate groups together with the "
            "available supporting fields and source documentation."
        )

    if result.limitations:
        attention.append(
            "Consider the recorded execution limitations before "
            "drawing conclusions from the duplicate analysis."
        )

    attention.append(
        "A repeated invoice number identifies records for scrutiny; "
        "it does not by itself establish a duplicate payment, error, "
        "control failure or fraud."
    )

    return tuple(attention)


def _table_columns(
    exceptions: tuple[ProcedureExceptionRecord, ...],
) -> tuple[DashboardTableColumn, ...]:
    """Return useful GL-001 exception explorer columns."""

    columns: list[DashboardTableColumn] = [
        DashboardTableColumn(
            key="source_row",
            label="Source Row",
        ),
        DashboardTableColumn(
            key="invoice_number",
            label="Invoice Number",
        ),
        DashboardTableColumn(
            key="duplicate_group_size",
            label="Group Size",
        ),
        DashboardTableColumn(
            key="vendor_relationship",
            label="Vendor Relationship",
        ),
    ]

    optional_columns = (
        (
            "vendor_code",
            "Vendor Code",
        ),
        (
            "vendor_name",
            "Vendor Name",
        ),
        (
            "transaction_date",
            "Date",
        ),
        (
            "transaction_amount",
            "Amount",
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
            "entry_user",
            "Prepared By",
        ),
        (
            "approval_user",
            "Approved By",
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

    return tuple(columns)


def _table_row(
    exception: ProcedureExceptionRecord,
) -> DashboardTableRow:
    """Convert one GL-001 exception to a dashboard row."""

    values: dict[str, str] = {
        "source_row": str(exception.source_row_number),
        "record_id": exception.source_record_id,
        "reason": exception.reason,
    }

    for key, raw_value in exception.values.items():
        values[key] = _display_value(raw_value)

    relationship = values.get(
        "vendor_relationship",
        "",
    ).casefold()

    groups = {
        "all",
    }

    if relationship == "same vendor":
        groups.add("same_vendor")
    elif relationship == "multiple vendors":
        groups.add("multiple_vendors")
    else:
        groups.add("not_assessable")

    if _as_int(exception.values.get("duplicate_group_size")) >= 3:
        groups.add("three_plus")

    return DashboardTableRow(
        values=values,
        groups=frozenset(groups),
    )


def _display_value(
    value: object,
) -> str:
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


def _as_int(
    value: object,
) -> int:
    """Return an integer metric with a safe zero fallback."""

    if value is None:
        return 0

    try:
        return int(value)
    except TypeError, ValueError:
        return 0
