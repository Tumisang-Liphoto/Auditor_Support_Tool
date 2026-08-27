"""Tests for the GL-006 result dashboard presenter."""

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
    optional_analysis_available: bool = True,
) -> ProcedureResult:
    """Return a representative GL-006 result."""

    request = AuditExecutionRequest.create(
        procedure_id="GL006",
        dataset_id="dataset-1",
    )

    context = ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )

    exception = ProcedureExceptionRecord.create(
        source_record_id="dataset-1:row-2",
        source_row_number=2,
        reason_code="SAME_ENTRY_AND_APPROVAL_USER",
        reason=("Same user entered and approved transaction - further audit scrutiny required."),
        values={
            "entry_user": "Alice",
            "approval_user": "Alice",
            "normalised_user": "alice",
            **(
                {
                    "journal_number": "J001",
                    "transaction_amount": 100,
                    "account_code": "4000",
                }
                if optional_analysis_available
                else {}
            ),
        },
    )

    return ProcedureResult.create(
        context=context,
        population_count=5,
        records_evaluated_count=4,
        exception_records=(exception,),
        exclusion_counts={
            "blank_entry_user": 1,
        },
        limitations=(
            "System, service and shared accounts are not automatically "
            "excluded in GL-006 version 1.0; auditor review is required.",
        ),
        metrics={
            "same_user_exceptions": 1,
            "distinct_conflicting_users": 1,
            "journal_number_available": optional_analysis_available,
            "affected_journals": 1 if optional_analysis_available else 0,
            "account_code_available": optional_analysis_available,
            "affected_accounts": 1 if optional_analysis_available else 0,
            "blank_entry_user_count": 1,
            "blank_approval_user_count": 0,
            "invalid_entry_user_count": 0,
            "invalid_approval_user_count": 0,
        },
    )


def test_gl006_presenter_builds_headline_metrics() -> None:
    """GL-006 should expose useful headline SoD metrics."""

    presentation = present_result(
        procedure_id="GL006",
        result=create_result(),
    )

    assert tuple(metric.title for metric in presentation.metrics) == (
        "Population",
        "Evaluated",
        "SoD Exceptions",
        "Exception %",
    )
    assert tuple(metric.value for metric in presentation.metrics) == (
        "5",
        "4",
        "1",
        "25.00%",
    )
    assert presentation.risk_title == "Segregation-of-Duties Analysis"
    assert presentation.risk_indicators[0].value == "1"


def test_gl006_presenter_builds_useful_exception_columns() -> None:
    """The exception explorer should retain user and optional context."""

    presentation = present_result(
        procedure_id="GL006",
        result=create_result(),
    )

    column_keys = tuple(column.key for column in presentation.table.columns)

    assert column_keys[:3] == (
        "source_row",
        "entry_user",
        "approval_user",
    )
    assert "journal_number" in column_keys
    assert "transaction_amount" in column_keys
    assert "account_code" in column_keys


def test_gl006_presenter_uses_na_when_optional_analysis_is_unavailable() -> None:
    """Unavailable helpful fields must be shown as N/A rather than zero."""

    presentation = present_result(
        procedure_id="GL006",
        result=create_result(optional_analysis_available=False),
    )

    assert presentation.risk_indicators[1].value == "N/A"
    assert presentation.risk_indicators[2].value == "N/A"
    assert presentation.risk_indicators[1].available is False
    assert presentation.risk_indicators[2].available is False
