"""Tests for the generic structured audit procedure report."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

import pytest

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_procedure_report_builder import (
    AuditProcedureReportBuilder,
)
from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReportSection,
    normalise_report_value,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)


def _definition(
    procedure_id: str = "GL006",
) -> ProcedureDefinition:
    return ProcedureDefinition.create(
        procedure_id=procedure_id,
        name="Segregation of Duties",
        category="General Ledger",
        description=("Identifies transactions where the entry and approval users are the same."),
        procedure_version="1.0",
    )


def _result() -> ProcedureResult:
    request = AuditExecutionRequest.create(
        procedure_id="GL006",
        dataset_id="dataset-gl",
    )
    context = ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        audit_period_start="2023-04-01",
        audit_period_end="2024-03-31",
        parameters={
            "case_sensitive": False,
        },
    )

    exceptions = (
        ProcedureExceptionRecord.create(
            source_record_id="dataset-gl:row-12",
            source_row_number=12,
            reason_code="same_entry_approval_user",
            reason="Entry User and Approval User are the same.",
            values={
                "entry_user": "finance.manager",
                "approval_user": "finance.manager",
                "transaction_date": date(2023, 8, 14),
                "transaction_amount": Decimal("125000.50"),
            },
            related_value=Decimal("125000.50"),
        ),
        ProcedureExceptionRecord.create(
            source_record_id="dataset-gl:row-19",
            source_row_number=19,
            reason_code="same_entry_approval_user",
            reason="Entry User and Approval User are the same.",
            values={
                "entry_user": "chief.accountant",
                "approval_user": "chief.accountant",
                "transaction_date": date(2023, 8, 21),
                "transaction_amount": Decimal("84000.00"),
            },
            related_value=Decimal("84000.00"),
        ),
    )

    return ProcedureResult.create(
        context=context,
        population_count=10,
        records_evaluated_count=8,
        exception_records=exceptions,
        exclusion_counts={
            "blank_entry_or_approval_user": 2,
        },
        related_value_total=Decimal("209000.50"),
        limitations=("Shared or service accounts require auditor interpretation.",),
        metrics={
            "distinct_conflicting_users": 2,
            "top_user_concentration_pct": 50.0,
            "analysis_date": date(2024, 3, 31),
            "user_analysis": [
                {
                    "user": "finance.manager",
                    "self_approvals": 1,
                    "amount": Decimal("125000.50"),
                },
                {
                    "user": "chief.accountant",
                    "self_approvals": 1,
                    "amount": Decimal("84000.00"),
                },
            ],
        },
    )


def test_report_builder_captures_complete_procedure_result() -> None:
    report = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
    )

    assert report.identity.procedure_id == "GL006"
    assert report.identity.display_id == "GL-006"
    assert report.identity.name == "Segregation of Duties"
    assert report.identity.category == "General Ledger"
    assert report.identity.procedure_version == "1.0"

    assert report.scope.dataset_id == "dataset-gl"
    assert report.scope.audit_period_start == "2023-04-01"
    assert report.scope.audit_period_end == "2024-03-31"
    assert report.scope.parameters == {
        "case_sensitive": False,
    }

    assert report.summary.population_count == 10
    assert report.summary.records_evaluated_count == 8
    assert report.summary.excluded_record_count == 2
    assert report.summary.exception_count == 2
    assert report.summary.exception_rate == pytest.approx(25.0)
    assert report.summary.related_value_total == "209000.50"

    assert report.exclusion_counts == {
        "blank_entry_or_approval_user": 2,
    }
    assert len(report.exceptions) == 2
    assert report.exceptions[0].source_row_number == 12
    assert report.exceptions[0].values["transaction_amount"] == ("125000.50")
    assert report.exceptions[0].values["transaction_date"] == ("2023-08-14")


def test_report_is_detached_from_result_nested_values() -> None:
    result = _result()

    report = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=result,
    )

    result.metrics["user_analysis"][0]["user"] = "changed"

    assert report.metrics["user_analysis"][0]["user"] == "finance.manager"


def test_report_supports_domain_supplied_analysis_sections() -> None:
    section = AuditProcedureReportSection.create(
        title="Self-Approval by User",
        narrative=("Two users account for all identified self-approval exceptions."),
        data={
            "users": 2,
            "highest_count": 1,
        },
    )

    report = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
        analysis_sections=(section,),
    )

    assert report.analysis_sections == (section,)
    assert report.analysis_sections[0].data == {
        "users": 2,
        "highest_count": 1,
    }


def test_report_json_is_complete_and_json_safe() -> None:
    report = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
    )

    payload = json.loads(report.to_json())

    assert payload["schema_version"] == 1
    assert payload["identity"]["procedure_id"] == "GL006"
    assert payload["summary"]["exception_count"] == 2
    assert payload["metrics"]["analysis_date"] == "2024-03-31"
    assert payload["metrics"]["user_analysis"][0]["amount"] == "125000.50"
    assert len(payload["report_fingerprint"]) == 64


def test_report_fingerprint_is_stable_for_same_report() -> None:
    first = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
    )
    second = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
    )

    assert first.report_fingerprint == second.report_fingerprint
    assert len(first.report_fingerprint) == 64


def test_report_fingerprint_changes_when_analysis_changes() -> None:
    first = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
    )
    second = AuditProcedureReportBuilder().build(
        definition=_definition(),
        result=_result(),
        analysis_sections=(
            AuditProcedureReportSection.create(
                title="Additional Analysis",
                narrative="A procedure-specific observation.",
            ),
        ),
    )

    assert first.report_fingerprint != second.report_fingerprint


def test_report_builder_rejects_wrong_procedure_definition() -> None:
    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        AuditProcedureReportBuilder().build(
            definition=_definition("GL003"),
            result=_result(),
        )


def test_report_section_requires_title() -> None:
    with pytest.raises(
        ValueError,
        match="title",
    ):
        AuditProcedureReportSection.create(
            title="   ",
        )


def test_report_value_normalisation_supports_common_types() -> None:
    class Status(StrEnum):
        READY = "ready"

    value = {
        "amount": Decimal("123.45"),
        "date": date(2024, 1, 31),
        "timestamp": datetime(2024, 1, 31, 12, 30),
        "status": Status.READY,
        "tuple": ("a", Decimal("2.50")),
        "set": {"b", "a"},
    }

    assert normalise_report_value(value) == {
        "amount": "123.45",
        "date": "2024-01-31",
        "timestamp": "2024-01-31T12:30:00",
        "status": "ready",
        "tuple": ["a", "2.50"],
        "set": ["a", "b"],
    }


def test_report_value_normalisation_rejects_unknown_objects() -> None:
    with pytest.raises(
        TypeError,
        match="Unsupported",
    ):
        normalise_report_value(object())
