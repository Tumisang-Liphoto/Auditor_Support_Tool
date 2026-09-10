"""Tests for the controlled audit-report AI handoff."""

from __future__ import annotations

from pathlib import Path

import pytest

from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReport,
    AuditProcedureReportIdentity,
    AuditProcedureReportScope,
    AuditProcedureReportSummary,
)
from auditor_support_tool.services.audit_report_ai_handoff import (
    AuditReportAIHandoffError,
    AuditReportAIHandoffService,
    AuditReportAIPackageBuilder,
)
from auditor_support_tool.services.openwebui_client import (
    OpenWebUIAnalysisResult,
)
from auditor_support_tool.services.openwebui_settings_service import (
    OpenWebUISettings,
    OpenWebUISettingsService,
)


class MemoryCredentialStore:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get_secret(self, target: str) -> str | None:
        return self.values.get(target)

    def set_secret(self, target: str, secret: str) -> None:
        self.values[target] = secret

    def delete_secret(self, target: str) -> None:
        self.values.pop(target, None)


class StubClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def analyse_audit_report(
        self,
        **kwargs,
    ) -> OpenWebUIAnalysisResult:
        self.calls.append(dict(kwargs))

        return OpenWebUIAnalysisResult(
            chat_id="chat-123",
            chat_url="http://ai:3000/c/chat-123",
            model=str(kwargs["model"]),
            uploaded_file_id="file-123",
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


def _settings_service(
    tmp_path: Path,
) -> tuple[
    OpenWebUISettingsService,
    MemoryCredentialStore,
]:
    credentials = MemoryCredentialStore()

    return (
        OpenWebUISettingsService(
            settings_file=tmp_path / "settings.ini",
            credential_store=credentials,
        ),
        credentials,
    )


def test_ai_package_contains_complete_structured_report() -> None:
    report = _report()

    package = AuditReportAIPackageBuilder().build(report)

    assert package.filename == ("GL-006_Audit_Procedure_Report.json")
    assert package.report_fingerprint == (report.report_fingerprint)
    assert package.exception_count == 57
    assert b'"procedure_id": "GL006"' in package.content
    assert b'"exception_count": 57' in package.content


def test_ai_prompt_preserves_audit_boundary() -> None:
    prompt = AuditReportAIPackageBuilder().build(_report()).prompt

    assert "Do not describe an exception as fraud" in prompt
    assert "Auditor judgement" in prompt
    assert "Report fingerprint" in prompt


def test_handoff_uses_saved_model_and_credential(
    tmp_path: Path,
) -> None:
    service, _ = _settings_service(tmp_path)
    client = StubClient()

    saved = service.save_settings(
        OpenWebUISettings(
            enabled=True,
            base_url="http://ai:3000",
            default_model="qwen-audit",
        )
    )
    service.save_api_key(
        base_url=saved.base_url,
        api_key="sk-secret",
    )

    result = AuditReportAIHandoffService(
        settings_service=service,
        client=client,
    ).send_report(_report())

    assert result.chat_id == "chat-123"
    assert len(client.calls) == 1
    assert client.calls[0]["api_key"] == "sk-secret"
    assert client.calls[0]["model"] == "qwen-audit"


def test_handoff_blocks_when_integration_is_disabled(
    tmp_path: Path,
) -> None:
    service, _ = _settings_service(tmp_path)

    service.save_settings(
        OpenWebUISettings(
            enabled=False,
            base_url="http://ai:3000",
            default_model="qwen-audit",
        )
    )

    with pytest.raises(
        AuditReportAIHandoffError,
        match="disabled",
    ):
        AuditReportAIHandoffService(
            settings_service=service,
            client=StubClient(),
        ).send_report(_report())


def test_handoff_requires_default_model(
    tmp_path: Path,
) -> None:
    service, _ = _settings_service(tmp_path)

    service.save_settings(
        OpenWebUISettings(
            enabled=True,
            base_url="http://ai:3000",
        )
    )

    with pytest.raises(
        AuditReportAIHandoffError,
        match="default OpenWebUI model",
    ):
        AuditReportAIHandoffService(
            settings_service=service,
            client=StubClient(),
        ).send_report(_report())


def test_handoff_requires_saved_api_key(
    tmp_path: Path,
) -> None:
    service, _ = _settings_service(tmp_path)

    service.save_settings(
        OpenWebUISettings(
            enabled=True,
            base_url="http://ai:3000",
            default_model="qwen-audit",
        )
    )

    with pytest.raises(
        AuditReportAIHandoffError,
        match="No saved OpenWebUI API key",
    ):
        AuditReportAIHandoffService(
            settings_service=service,
            client=StubClient(),
        ).send_report(_report())
