"""Tests for Stage 7E evidence-grounded AI analysis instructions."""

from __future__ import annotations

import json

from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReport,
    AuditProcedureReportIdentity,
    AuditProcedureReportScope,
    AuditProcedureReportSummary,
)
from auditor_support_tool.services.audit_report_ai_handoff import (
    AuditReportAIPackageBuilder,
)


def _report() -> AuditProcedureReport:
    return AuditProcedureReport(
        identity=AuditProcedureReportIdentity(
            procedure_id="GL006",
            display_id="GL-006",
            name="Segregation of Duties",
            category="General Ledger",
            description="Same user entry and approval test.",
            procedure_version="1.0",
        ),
        scope=AuditProcedureReportScope(
            dataset_id="dataset-1",
            audit_period_start="2023-04-01",
            audit_period_end="2024-03-31",
            parameters={},
        ),
        summary=AuditProcedureReportSummary(
            population_count=2000,
            records_evaluated_count=2000,
            excluded_record_count=0,
            exception_count=57,
            exception_rate=2.85,
            related_value_total=None,
        ),
        exclusion_counts={},
        metrics={"distinct_conflicting_users": 4},
        limitations=("Auditor review required.",),
        audit_use_statement="Not a confirmed finding.",
        exceptions=(),
        analysis_sections=(),
        execution_id="exec-1",
        created_at="2026-08-31T08:00:00+00:00",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )


def _package():
    return AuditReportAIPackageBuilder().build(_report())


def test_uploaded_package_contains_analysis_contract_and_report() -> None:
    payload = json.loads(_package().content.decode())

    assert "analysis_contract" in payload
    assert "audit_procedure_report" in payload
    assert payload["audit_procedure_report"]["summary"]["exception_count"] == 57


def test_prompt_does_not_equate_exception_rate_with_non_compliance() -> None:
    prompt = _package().prompt

    assert "exception means only" in prompt
    assert "Do not convert the exception rate" in prompt
    assert "non-compliance rate" in prompt


def test_prompt_requires_evidence_for_numerical_patterns() -> None:
    prompt = _package().prompt

    assert "Numerator" in prompt
    assert "Denominator" in prompt
    assert "Field or fields used" in prompt
    assert "Calculation or grouping rule" in prompt
    assert "Supporting source-row references" in prompt


def test_prompt_blocks_unsupported_text_classifications() -> None:
    prompt = _package().prompt

    assert "Do not invent classifications" in prompt
    assert "exact field" in prompt
    assert "matching terms or grouping rule" in prompt


def test_prompt_separates_fact_pattern_hypothesis_and_unknown() -> None:
    prompt = _package().prompt

    assert "REPORT FACT" in prompt
    assert "DERIVED PATTERN" in prompt
    assert "HYPOTHESIS" in prompt
    assert "NOT ESTABLISHED" in prompt


def test_prompt_requires_explicit_statement_when_evidence_is_insufficient() -> None:
    prompt = _package().prompt

    assert "Not established by the supplied audit report." in prompt


def test_prompt_requires_matters_not_established_section() -> None:
    prompt = _package().prompt

    assert "7. MATTERS NOT ESTABLISHED" in prompt
    assert "fraud" in prompt
    assert "non-compliance" in prompt
    assert "control failure" in prompt
    assert "financial misstatement" in prompt


def test_prompt_preserves_auditor_judgement_and_corroboration() -> None:
    prompt = _package().prompt

    assert "Auditor judgement" in prompt
    assert "corroboration remain required" in prompt


def test_analysis_contract_is_embedded_in_uploaded_file() -> None:
    payload = json.loads(_package().content.decode())
    contract = payload["analysis_contract"]

    assert contract["authoritative_boundary"] == (
        "The audit procedure, not the AI, determines which records are exceptions."
    )
    assert "NOT ESTABLISHED" in contract["evidence_statuses"]
    assert any("source-row references" in rule for rule in contract["strict_rules"])
