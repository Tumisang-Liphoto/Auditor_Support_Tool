"""Tests for Stage 7F deterministic direct evidence delivery."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from auditor_support_tool.services.audit_report_ai_handoff import (
    AuditReportAIHandoffError,
    AuditReportAIPackageBuilder,
)


@dataclass(frozen=True, slots=True)
class StubAuditReport:
    """Minimal report-shaped object for package-builder boundary tests."""

    exception_value: str = "Payroll allocation"

    @property
    def identity(self) -> SimpleNamespace:
        return SimpleNamespace(
            display_id="GL-006",
            name="Segregation of Duties",
        )

    @property
    def summary(self) -> SimpleNamespace:
        return SimpleNamespace(
            population_count=2000,
            records_evaluated_count=2000,
            exception_count=1,
            exception_rate=0.05,
        )

    @property
    def report_fingerprint(self) -> str:
        return "f" * 64

    def to_json(
        self,
        *,
        indent: int | None = None,
    ) -> str:
        payload = {
            "identity": {
                "procedure_id": "GL006",
                "display_id": "GL-006",
                "name": "Segregation of Duties",
            },
            "summary": {
                "population_count": 2000,
                "records_evaluated_count": 2000,
                "exception_count": 1,
                "exception_rate": 0.05,
            },
            "exceptions": [
                {
                    "source_record_id": "dataset-1:row-42",
                    "source_row_number": 42,
                    "reason": "Entry and approval user are the same.",
                    "values": {
                        "transaction_description": self.exception_value,
                        "entry_user": "finance.manager",
                        "approval_user": "finance.manager",
                    },
                }
            ],
            "report_fingerprint": self.report_fingerprint,
        }

        return json.dumps(
            payload,
            indent=indent,
        )


def _report(
    *,
    exception_value: str = "Payroll allocation",
) -> StubAuditReport:
    return StubAuditReport(
        exception_value=exception_value,
    )


def _build(
    report: StubAuditReport,
    *,
    max_inline_bytes: int | None = None,
):
    if max_inline_bytes is None:
        builder = AuditReportAIPackageBuilder()
    else:
        builder = AuditReportAIPackageBuilder(max_inline_bytes=max_inline_bytes)

    return builder.build(report)  # type: ignore[arg-type]


def test_prompt_embeds_complete_authoritative_report_json() -> None:
    package = _build(_report())

    assert "BEGIN AUTHORITATIVE AUDIT REPORT JSON" in package.prompt
    assert "END AUTHORITATIVE AUDIT REPORT JSON" in package.prompt
    assert '"source_row_number": 42' in package.prompt
    assert '"transaction_description": "Payroll allocation"' in package.prompt


def test_prompt_does_not_depend_on_openwebui_retrieval() -> None:
    prompt = _build(_report()).prompt

    assert "Analyse that embedded JSON directly" in prompt
    assert "Do not depend on file retrieval" in prompt
    assert "Sources indicator" in prompt


def test_attached_and_inline_evidence_use_same_serialized_payload() -> None:
    package = _build(_report())

    payload_text = package.content.decode()

    assert payload_text in package.prompt
    assert package.inline_evidence_bytes == len(package.content)
    assert package.evidence_sha256 == hashlib.sha256(package.content).hexdigest()


def test_embedded_payload_contains_analysis_contract_and_report() -> None:
    package = _build(_report())
    payload = json.loads(package.content.decode())

    assert "analysis_contract" in payload
    assert "audit_procedure_report" in payload
    assert payload["audit_procedure_report"]["exceptions"][0]["source_row_number"] == 42


def test_prompt_blocks_unsupported_high_or_low_assessments() -> None:
    prompt = _build(_report()).prompt

    assert "as high, low" in prompt
    assert "contains a benchmark" in prompt


def test_prompt_blocks_premature_corrective_action_question() -> None:
    prompt = _build(_report()).prompt

    assert "Do not ask management what corrective action will be taken" in prompt
    assert "condition requiring correction" in prompt


def test_prompt_blocks_duplicate_derived_patterns() -> None:
    prompt = _build(_report()).prompt

    assert "Do not repeat the same derived pattern" in prompt


def test_oversized_report_is_blocked_without_truncation() -> None:
    with pytest.raises(
        AuditReportAIHandoffError,
        match="Nothing was truncated or silently omitted",
    ):
        _build(
            _report(exception_value="x" * 500),
            max_inline_bytes=100,
        )


def test_inline_limit_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="at least 1 byte",
    ):
        AuditReportAIPackageBuilder(max_inline_bytes=0)


def test_evidence_hash_is_disclosed_in_prompt() -> None:
    package = _build(_report())

    assert f"Authoritative evidence SHA-256: {package.evidence_sha256}" in package.prompt
