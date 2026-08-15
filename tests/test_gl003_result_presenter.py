"""Tests for the GL-003 result dashboard presenter."""

from __future__ import annotations

from decimal import Decimal

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.presentation.result_presenter_registry import (
    present_result,
)


def _context() -> ProcedureRunContext:
    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id="dataset-123",
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
    )


def _exceptions() -> tuple[
    ProcedureExceptionRecord,
    ...,
]:
    return (
        ProcedureExceptionRecord.create(
            source_record_id="dataset-123:row-2",
            source_row_number=2,
            reason_code="WEEKEND_TRANSACTION",
            reason="Transaction date falls on Saturday.",
            values={
                "transaction_date": "2026-01-03",
                "day_of_week": "Saturday",
                "journal_number": "J001",
                "debit_amount": Decimal("5000"),
                "risk_indicators": (
                    "high_value",
                    "manual_journal",
                ),
                "high_risk": True,
            },
        ),
        ProcedureExceptionRecord.create(
            source_record_id="dataset-123:row-3",
            source_row_number=3,
            reason_code="WEEKEND_TRANSACTION",
            reason="Transaction date falls on Sunday.",
            values={
                "transaction_date": "2026-01-04",
                "day_of_week": "Sunday",
                "journal_number": "J002",
                "credit_amount": Decimal("250"),
                "risk_indicators": (),
                "high_risk": False,
            },
        ),
    )


def test_gl003_presenter_builds_approved_headline_metrics() -> None:
    result = ProcedureResult.create(
        context=_context(),
        population_count=10,
        records_evaluated_count=10,
        exception_records=_exceptions(),
        metrics={
            "saturday_transactions": 1,
            "sunday_transactions": 1,
            "weekend_percentage": 20.0,
            "high_risk_available": True,
            "high_risk_weekend_count": 1,
            "evaluated_risk_indicators": (
                "high_value",
                "manual_journal",
            ),
            "unavailable_risk_indicators": ("same_preparer_approver",),
            "high_value_available": True,
            "high_value_threshold": Decimal("4000"),
            "high_value_weekend_count": 1,
            "manual_journal_available": True,
            "manual_journal_values": ("manual",),
            "manual_journal_weekend_count": 1,
            "same_preparer_approver_available": False,
            "debit_summary_available": True,
            "credit_summary_available": True,
            "saturday_debit_total": Decimal("5000"),
            "saturday_credit_total": Decimal("0"),
            "sunday_debit_total": Decimal("0"),
            "sunday_credit_total": Decimal("250"),
            "weekend_debit_total": Decimal("5000"),
            "weekend_credit_total": Decimal("250"),
        },
    )

    presentation = present_result(
        procedure_id="GL003",
        result=result,
    )

    assert tuple(metric.title for metric in presentation.metrics) == (
        "Saturday",
        "Sunday",
        "Weekend %",
        "High Risk",
    )
    assert tuple(metric.value for metric in presentation.metrics) == (
        "1",
        "1",
        "20.0%",
        "1",
    )

    assert presentation.risk_indicators[0].value == "1"
    assert presentation.risk_indicators[1].value == "1"
    assert presentation.risk_indicators[2].value == "N/A"


def test_gl003_presenter_preserves_na_semantics() -> None:
    result = ProcedureResult.create(
        context=_context(),
        population_count=2,
        records_evaluated_count=2,
        exception_records=_exceptions(),
        limitations=("Additional analysis unavailable.",),
        metrics={
            "saturday_transactions": 1,
            "sunday_transactions": 1,
            "weekend_percentage": 100.0,
            "high_risk_available": False,
            "high_risk_weekend_count": 0,
            "evaluated_risk_indicators": (),
            "unavailable_risk_indicators": (
                "high_value",
                "manual_journal",
                "same_preparer_approver",
            ),
            "high_value_available": False,
            "high_value_threshold": None,
            "manual_journal_available": False,
            "manual_journal_values": (),
            "same_preparer_approver_available": False,
            "debit_summary_available": False,
            "credit_summary_available": False,
        },
    )

    presentation = present_result(
        procedure_id="GL003",
        result=result,
    )

    assert presentation.metrics[3].value == "N/A"
    assert all(indicator.value == "N/A" for indicator in presentation.risk_indicators)

    assert presentation.summary is not None
    assert presentation.summary.rows[0].values == (
        "N/A",
        "N/A",
    )


def test_gl003_presenter_builds_table_filters_and_groups() -> None:
    result = ProcedureResult.create(
        context=_context(),
        population_count=2,
        records_evaluated_count=2,
        exception_records=_exceptions(),
        metrics={
            "saturday_transactions": 1,
            "sunday_transactions": 1,
            "weekend_percentage": 100.0,
            "high_risk_available": True,
            "high_risk_weekend_count": 1,
            "evaluated_risk_indicators": ("high_value",),
            "unavailable_risk_indicators": (
                "manual_journal",
                "same_preparer_approver",
            ),
            "high_value_available": True,
            "high_value_threshold": Decimal("4000"),
            "high_value_weekend_count": 1,
            "manual_journal_available": False,
            "manual_journal_values": (),
            "same_preparer_approver_available": False,
            "debit_summary_available": True,
            "credit_summary_available": True,
        },
    )

    presentation = present_result(
        procedure_id="GL003",
        result=result,
    )

    assert tuple(table_filter.key for table_filter in presentation.table.filters) == (
        "all",
        "high_risk",
        "saturday",
        "sunday",
    )

    saturday_row = presentation.table.rows[0]
    sunday_row = presentation.table.rows[1]

    assert "saturday" in saturday_row.groups
    assert "high_risk" in saturday_row.groups
    assert "sunday" in sunday_row.groups
    assert "high_risk" not in sunday_row.groups
