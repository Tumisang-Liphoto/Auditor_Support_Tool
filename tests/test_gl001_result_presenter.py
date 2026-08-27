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
        "Population",
        "Tested",
        "Duplicate Groups",
        "Records Flagged",
    )

    assert tuple(metric.value for metric in presentation.metrics) == (
        "5",
        "4",
        "1",
        "3",
    )

    assert presentation.risk_title == "Duplicate Pattern Analysis"
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
