"""Resolve procedure results into reusable dashboard presentations."""

from __future__ import annotations

from collections.abc import Callable

from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
)
from auditor_support_tool.presentation.gl003_result_presenter import (
    present_gl003_result,
)
from auditor_support_tool.presentation.result_dashboard_models import (
    DashboardMetric,
    DashboardTable,
    DashboardTableColumn,
    DashboardTableFilter,
    DashboardTableRow,
    ResultDashboardPresentation,
)

ResultPresenter = Callable[
    [ProcedureResult],
    ResultDashboardPresentation,
]

_PRESENTERS: dict[str, ResultPresenter] = {
    "GL003": present_gl003_result,
}


def present_result(
    *,
    procedure_id: str,
    result: ProcedureResult,
) -> ResultDashboardPresentation:
    """Return the registered or generic dashboard presentation."""

    presenter = _PRESENTERS.get(procedure_id.strip().upper())

    if presenter is not None:
        return presenter(result)

    return _present_generic_result(result)


def _present_generic_result(
    result: ProcedureResult,
) -> ResultDashboardPresentation:
    """Build the generic fallback dashboard."""

    observations: list[str] = []

    if result.excluded_record_count:
        observations.append(
            f"{result.excluded_record_count:,} records were excluded from evaluation."
        )

    observations.extend(result.limitations)

    if not observations:
        observations.append("The procedure completed without recorded execution limitations.")

    rows = tuple(
        DashboardTableRow(
            values={
                "source_row": str(exception.source_row_number),
                "reason": exception.reason,
                "record_id": (exception.source_record_id),
                "details": ", ".join(f"{key}={value}" for key, value in exception.values.items())
                or "—",
            },
        )
        for exception in result.exception_records
    )

    return ResultDashboardPresentation(
        metrics=(
            DashboardMetric(
                title="Population",
                value=f"{result.population_count:,}",
                detail="Source records",
                icon_name="fa5s.database",
            ),
            DashboardMetric(
                title="Evaluated",
                value=(f"{result.records_evaluated_count:,}"),
                detail="Records evaluated",
                icon_name="fa5s.check-circle",
                emphasis="success",
            ),
            DashboardMetric(
                title="Exceptions",
                value=f"{result.exception_count:,}",
                detail="Records requiring review",
                icon_name="fa5s.exclamation-triangle",
                emphasis="risk",
            ),
            DashboardMetric(
                title="Exception %",
                value=f"{result.exception_rate:.2f}%",
                detail="Of evaluated records",
                icon_name="fa5s.percentage",
                emphasis="information",
            ),
        ),
        risk_title="Audit Analysis",
        risk_description=("Procedure-specific analysis is not yet available for this result."),
        risk_indicators=(),
        summary=None,
        observations=tuple(observations),
        attention_areas=(result.audit_use_statement,),
        table=DashboardTable(
            title=(
                f"{result.exception_count:,} Exception"
                + ("" if result.exception_count == 1 else "s")
            ),
            description=("Source-linked records identified by the audit procedure."),
            columns=(
                DashboardTableColumn(
                    key="source_row",
                    label="Source Row",
                ),
                DashboardTableColumn(
                    key="reason",
                    label="Reason",
                ),
                DashboardTableColumn(
                    key="record_id",
                    label="Record ID",
                ),
                DashboardTableColumn(
                    key="details",
                    label="Details",
                ),
            ),
            rows=rows,
            filters=(
                DashboardTableFilter(
                    key="all",
                    label="All",
                ),
            ),
            source_note=(
                "Each exception retains its source record "
                "identifier for audit evidence traceability."
            ),
        ),
        audit_use_statement=result.audit_use_statement,
    )
