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


def _exception(
    *,
    row_number: int,
    user: str,
    amount: int = 100,
) -> ProcedureExceptionRecord:
    """Return one representative self-approval exception."""

    return ProcedureExceptionRecord.create(
        source_record_id=f"dataset-1:row-{row_number}",
        source_row_number=row_number,
        reason_code="SAME_ENTRY_AND_APPROVAL_USER",
        reason=("Same user entered and approved transaction - further audit scrutiny required."),
        values={
            "entry_user": user,
            "approval_user": user,
            "normalised_user": user.casefold(),
            "journal_number": f"J{row_number:03d}",
            "transaction_amount": amount,
            "account_code": "4000",
        },
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
            "highest_self_approval_count": 1,
            "top_user": "Alice",
            "top_user_concentration_pct": 100.0,
            "user_self_approval_analysis": (
                {
                    "user": "Alice",
                    "normalised_user": "alice",
                    "self_approvals": 1,
                    "exception_share_pct": 100.0,
                    "affected_journals": 1 if optional_analysis_available else 0,
                    "affected_accounts": 1 if optional_analysis_available else 0,
                    "transaction_amount_total": 100,
                    "transaction_amount_records": (1 if optional_analysis_available else 0),
                },
            ),
            "journal_number_available": optional_analysis_available,
            "affected_journals": 1 if optional_analysis_available else 0,
            "account_code_available": optional_analysis_available,
            "affected_accounts": 1 if optional_analysis_available else 0,
            "transaction_amount_available": optional_analysis_available,
            "blank_entry_user_count": 1,
            "blank_approval_user_count": 0,
            "invalid_entry_user_count": 0,
            "invalid_approval_user_count": 0,
        },
    )


def create_concentrated_result() -> ProcedureResult:
    """Return a result where one user dominates the SoD exceptions."""

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

    exceptions = (
        _exception(row_number=2, user="Alice", amount=100),
        _exception(row_number=3, user="Alice", amount=200),
        _exception(row_number=4, user="Alice", amount=300),
        _exception(row_number=5, user="Bob", amount=400),
    )

    return ProcedureResult.create(
        context=context,
        population_count=4,
        records_evaluated_count=4,
        exception_records=exceptions,
        metrics={
            "same_user_exceptions": 4,
            "distinct_conflicting_users": 2,
            "highest_self_approval_count": 3,
            "top_user": "Alice",
            "top_user_concentration_pct": 75.0,
            "user_self_approval_analysis": (
                {
                    "user": "Alice",
                    "normalised_user": "alice",
                    "self_approvals": 3,
                    "exception_share_pct": 75.0,
                    "affected_journals": 3,
                    "affected_accounts": 1,
                    "transaction_amount_total": 600,
                    "transaction_amount_records": 3,
                },
                {
                    "user": "Bob",
                    "normalised_user": "bob",
                    "self_approvals": 1,
                    "exception_share_pct": 25.0,
                    "affected_journals": 1,
                    "affected_accounts": 1,
                    "transaction_amount_total": 400,
                    "transaction_amount_records": 1,
                },
            ),
            "journal_number_available": True,
            "affected_journals": 4,
            "account_code_available": True,
            "affected_accounts": 1,
            "transaction_amount_available": True,
            "blank_entry_user_count": 0,
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
        "Evaluated Records",
        "Exceptions",
        "Exception Rate",
        "Distinct Identifiers",
    )
    assert tuple(metric.value for metric in presentation.metrics) == (
        "4",
        "1",
        "25.00%",
        "1",
    )
    assert presentation.risk_title == "Additional Analysis"
    assert "do not prove the same person" in presentation.risk_description
    assert "automatically excluded" in presentation.risk_description
    assert tuple(indicator.value for indicator in presentation.risk_indicators) == (
        "1",
        "100.0%",
    )


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


def test_gl006_presenter_builds_ranked_self_approval_summary() -> None:
    """The dashboard should describe which users drive self-approval exceptions."""

    presentation = present_result(
        procedure_id="GL006",
        result=create_concentrated_result(),
    )

    assert presentation.summary is not None
    assert presentation.summary.title == "Exceptions by User Identifier"
    assert presentation.summary.headers == (
        "Exceptions",
        "% of Exceptions",
        "Journals",
        "Amount",
    )
    assert tuple(row.label for row in presentation.summary.rows) == (
        "Alice",
        "Bob",
    )
    assert presentation.summary.rows[0].values == (
        "3",
        "75.0%",
        "3",
        "600.00",
    )
    assert any(
        "Alice was associated with the most exceptions" in observation
        for observation in presentation.observations
    )


def test_gl006_presenter_uses_na_when_optional_analysis_is_unavailable() -> None:
    """Unavailable helpful fields must be shown as N/A rather than zero."""

    presentation = present_result(
        procedure_id="GL006",
        result=create_result(optional_analysis_available=False),
    )

    assert presentation.summary is not None
    assert "Journal analysis not evaluated" in presentation.summary.description
    assert "Amount analysis not evaluated" in presentation.summary.description
    assert presentation.summary.rows[0].values == (
        "1",
        "100.0%",
        "N/A",
        "N/A",
    )


def test_gl006_presenter_distinguishes_zero_from_unevaluated() -> None:
    """Zero exceptions is valid; a rate needs an evaluated denominator."""
    for evaluated in (3, 0):
        result = ProcedureResult.create(
            context=create_result().context,
            population_count=3,
            records_evaluated_count=evaluated,
            exclusion_counts={"unusable_required_value": 3 - evaluated},
            exception_records=(),
            metrics={
                "distinct_conflicting_users": 0,
                "highest_self_approval_count": 0,
                "top_user_concentration_pct": 0,
            },
        )
        presentation = present_result(procedure_id="GL006", result=result)
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


def test_gl006_presenter_preserves_authoritative_exceptions() -> None:
    """Presentation must retain every exception and leave the result untouched."""
    from copy import deepcopy

    result = create_result()
    original = deepcopy(result)
    presentation = present_result(procedure_id="GL006", result=result)
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


def test_gl006_presenter_does_not_show_missing_headline_analysis_as_zero() -> None:
    result = ProcedureResult.create(
        context=create_result().context, population_count=2, records_evaluated_count=2
    )
    presentation = present_result(procedure_id="GL006", result=result)
    metrics = {metric.title: metric.value for metric in presentation.metrics}
    for title in ("Distinct Identifiers",):
        assert metrics[title] == "N/A"
    assert metrics["Exceptions"] == "0"
    assert metrics["Exception Rate"] == "0.00%"
