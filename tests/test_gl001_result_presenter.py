"""Tests for the GL-001 result dashboard presenter."""

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


def create_result(
    *,
    vendor_analysis_available: bool = True,
) -> ProcedureResult:
    """Return a representative GL-001 result."""

    request = AuditExecutionRequest.create(
        procedure_id="GL001",
        dataset_id="dataset-1",
    )

    context = ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )

    exceptions = (
        ProcedureExceptionRecord.create(
            source_record_id="dataset-1:row-2",
            source_row_number=2,
            reason_code="DUPLICATE_INVOICE_NUMBER",
            reason="Repeated invoice number — further audit scrutiny required.",
            values={
                "invoice_number": "INV-1001",
                "normalised_invoice_number": "inv-1001",
                "duplicate_group_id": "GL-001-GROUP-0001",
                "duplicate_group_size": 3,
                "vendor_relationship": (
                    "Same vendor" if vendor_analysis_available else "Not assessable"
                ),
                "vendor_code": "V001",
                "transaction_amount": 100,
            },
        ),
        ProcedureExceptionRecord.create(
            source_record_id="dataset-1:row-3",
            source_row_number=3,
            reason_code="DUPLICATE_INVOICE_NUMBER",
            reason="Repeated invoice number — further audit scrutiny required.",
            values={
                "invoice_number": "inv-1001",
                "normalised_invoice_number": "inv-1001",
                "duplicate_group_id": "GL-001-GROUP-0001",
                "duplicate_group_size": 3,
                "vendor_relationship": (
                    "Same vendor" if vendor_analysis_available else "Not assessable"
                ),
                "vendor_code": "V001",
                "transaction_amount": 100,
            },
        ),
        ProcedureExceptionRecord.create(
            source_record_id="dataset-1:row-4",
            source_row_number=4,
            reason_code="DUPLICATE_INVOICE_NUMBER",
            reason="Repeated invoice number — further audit scrutiny required.",
            values={
                "invoice_number": "INV-1001",
                "normalised_invoice_number": "inv-1001",
                "duplicate_group_id": "GL-001-GROUP-0001",
                "duplicate_group_size": 3,
                "vendor_relationship": (
                    "Same vendor" if vendor_analysis_available else "Not assessable"
                ),
                "vendor_code": "V001",
                "transaction_amount": 100,
            },
        ),
    )

    return ProcedureResult.create(
        context=context,
        population_count=5,
        records_evaluated_count=4,
        exception_records=exceptions,
        exclusion_counts={
            "blank_invoice_number": 1,
        },
        metrics={
            "duplicate_groups": 1,
            "flagged_records": 3,
            "additional_duplicate_records": 2,
            "blank_invoice_number_count": 1,
            "invalid_invoice_number_count": 0,
            "vendor_analysis_available": vendor_analysis_available,
            "same_vendor_groups": 1 if vendor_analysis_available else 0,
            "multiple_vendor_groups": 0,
            "vendor_not_assessable_groups": (0 if vendor_analysis_available else 1),
            "same_vendor_records": 3 if vendor_analysis_available else 0,
            "multiple_vendor_records": 0,
            "vendor_not_assessable_records": (0 if vendor_analysis_available else 3),
        },
        limitations=(
            ()
            if vendor_analysis_available
            else (
                "Vendor Code and Vendor Name are not mapped; "
                "vendor relationship analysis is unavailable.",
            )
        ),
    )


def test_gl001_presenter_builds_headline_metrics() -> None:
    """GL-001 should replace generic exception cards with useful metrics."""

    presentation = present_result(
        procedure_id="GL001",
        result=create_result(),
    )

    assert tuple(metric.title for metric in presentation.metrics) == (
        "Evaluated Records",
        "Exceptions",
        "Exception Rate",
        "Duplicate Groups",
    )

    assert tuple(metric.value for metric in presentation.metrics) == (
        "4",
        "3",
        "75.00%",
        "1",
    )

    assert presentation.risk_title == "Additional Analysis"
    assert presentation.risk_indicators[0].value == "2"
    assert presentation.risk_indicators[1].value == "1"


def test_gl001_presenter_builds_filters_groups_and_columns() -> None:
    """The exception explorer should support useful duplicate drill-down."""

    presentation = present_result(
        procedure_id="GL001",
        result=create_result(),
    )

    assert tuple(table_filter.key for table_filter in presentation.table.filters) == (
        "all",
        "same_vendor",
        "multiple_vendors",
        "not_assessable",
        "three_plus",
    )

    first_row = presentation.table.rows[0]

    assert "same_vendor" in first_row.groups
    assert "three_plus" in first_row.groups

    column_keys = tuple(column.key for column in presentation.table.columns)

    assert "invoice_number" in column_keys
    assert "vendor_code" in column_keys
    assert "transaction_amount" in column_keys


def test_gl001_presenter_uses_na_when_vendor_analysis_is_unavailable() -> None:
    """Unavailable optional vendor context must never be shown as zero."""

    presentation = present_result(
        procedure_id="GL001",
        result=create_result(
            vendor_analysis_available=False,
        ),
    )

    assert presentation.risk_indicators[1].value == "N/A"
    assert presentation.risk_indicators[2].value == "N/A"
    assert presentation.risk_indicators[1].available is False
    assert presentation.summary is not None
    assert presentation.summary.rows[0].label == "Not assessable"


def test_gl001_presenter_distinguishes_zero_from_unevaluated() -> None:
    """Zero exceptions is valid; a rate needs an evaluated denominator."""
    for evaluated in (3, 0):
        result = ProcedureResult.create(
            context=create_result().context,
            population_count=3,
            records_evaluated_count=evaluated,
            exclusion_counts={"unusable_required_value": 3 - evaluated},
            exception_records=(),
            metrics={
                "duplicate_groups": 0,
                "additional_duplicate_records": 0,
                "vendor_analysis_available": True,
                "same_vendor_groups": 0,
                "multiple_vendor_groups": 0,
            },
        )
        presentation = present_result(procedure_id="GL001", result=result)
        if evaluated:
            assert tuple(metric.value for metric in presentation.metrics) == (
                "3",
                "0",
                "0.00%",
                "0",
            )
        else:
            rate = next(
                metric for metric in presentation.metrics if metric.title == "Exception Rate"
            )
            assert rate.value == "N/A"
            assert rate.detail == "No records evaluated"
        assert presentation.table.rows == ()
        assert presentation.risk_title == "Additional Analysis"
        assert all(indicator.value in ("0", "0.0%") for indicator in presentation.risk_indicators)


def test_gl001_presenter_preserves_authoritative_exceptions() -> None:
    """Presentation must retain every exception and leave the result untouched."""
    from copy import deepcopy

    result = create_result()
    result.metrics["flagged_records"] = 99
    original = deepcopy(result)
    presentation = present_result(procedure_id="GL001", result=result)
    counts = {metric.title: metric.value for metric in presentation.metrics}
    assert counts["Exceptions"] == str(result.exception_count)
    assert counts["Exception Rate"] == f"{result.exception_rate:.2f}%"
    assert len(presentation.table.rows) == result.exception_count
    assert tuple(
        (row.values["record_id"], row.values["source_row"], row.values["reason"])
        for row in presentation.table.rows
    ) == tuple(
        (record.source_record_id, str(record.source_row_number), record.reason)
        for record in result.exception_records
    )
    assert result == original


def test_gl001_presenter_does_not_show_missing_headline_analysis_as_zero() -> None:
    result = ProcedureResult.create(
        context=create_result().context, population_count=2, records_evaluated_count=2
    )
    presentation = present_result(procedure_id="GL001", result=result)
    metrics = {metric.title: metric.value for metric in presentation.metrics}
    for title in ("Duplicate Groups",):
        assert metrics[title] == "N/A"
    assert metrics["Exceptions"] == "0"
    assert metrics["Exception Rate"] == "0.00%"
