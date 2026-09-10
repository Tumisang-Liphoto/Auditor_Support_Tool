"""Build and send evidence-grounded audit procedure reports to OpenWebUI."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReport,
)
from auditor_support_tool.services.openwebui_client import (
    OpenWebUIAnalysisResult,
    OpenWebUIClient,
)
from auditor_support_tool.services.openwebui_settings_service import (
    OpenWebUISettingsService,
)
from auditor_support_tool.services.windows_credential_service import (
    CredentialStoreError,
)

_DEFAULT_MAX_INLINE_BYTES = 64 * 1024


class AuditReportAIHandoffError(RuntimeError):
    """Raised when an audit report cannot be handed to the configured AI."""


@dataclass(frozen=True, slots=True)
class AuditReportAIPackage:
    """Controlled report payload sent to the internal AI service."""

    filename: str
    content: bytes
    prompt: str
    report_fingerprint: str
    exception_count: int
    evidence_sha256: str
    inline_evidence_bytes: int


class AuditReportAIPackageBuilder:
    """Create an evidence-grounded AI package from an authoritative report."""

    _ANALYSIS_CONTRACT = {
        "purpose": (
            "Assist the auditor with evidence-grounded interpretation of a "
            "completed deterministic audit procedure."
        ),
        "authoritative_boundary": (
            "The audit procedure, not the AI, determines which records are exceptions."
        ),
        "evidence_statuses": (
            "REPORT FACT",
            "DERIVED PATTERN",
            "HYPOTHESIS",
            "NOT ESTABLISHED",
        ),
        "strict_rules": (
            ("Treat an exception only as a record that met the configured audit-test criteria."),
            (
                "Do not describe an exception as fraud, error, non-compliance, "
                "a control failure, a misstatement or a confirmed audit finding "
                "unless the supplied report explicitly establishes that conclusion."
            ),
            (
                "Do not convert the exception rate into a non-compliance rate, "
                "error rate, fraud rate, control-failure rate or misstatement rate."
            ),
            (
                "Do not describe a rate, count, pattern or concentration as high, "
                "low, significant, unusual or acceptable unless the supplied report "
                "contains a benchmark or other evidence supporting that assessment."
            ),
            (
                "Every numerical pattern derived from exception records must state "
                "the numerator, denominator, field or fields used, grouping or "
                "calculation rule and supporting source-row references where available."
            ),
            (
                "Do not invent classifications that are not present in the report. "
                "If a text-based grouping is created, state the exact field, matching "
                "terms or grouping rule and supporting records."
            ),
            (
                "Clearly separate report facts, derived patterns, hypotheses and "
                "matters not established by the supplied report."
            ),
            (
                "Possible causes and explanations are hypotheses requiring "
                "corroboration, not established facts."
            ),
            (
                "Do not ask management what corrective action will be taken unless "
                "the supplied evidence first establishes a condition requiring "
                "correction."
            ),
            (
                'When evidence is insufficient, state: "Not established by the '
                'supplied audit report."'
            ),
            (
                "Auditor judgement, corroboration and professional assessment remain "
                "required before reaching an audit conclusion."
            ),
        ),
    }

    def __init__(
        self,
        *,
        max_inline_bytes: int = _DEFAULT_MAX_INLINE_BYTES,
    ) -> None:
        if max_inline_bytes < 1:
            raise ValueError("Maximum inline AI evidence size must be at least 1 byte.")

        self._max_inline_bytes = max_inline_bytes

    def build(
        self,
        report: AuditProcedureReport,
    ) -> AuditReportAIPackage:
        """Return attached and directly embedded authoritative evidence."""

        filename = f"{report.identity.display_id}_Audit_Procedure_Report.json"

        envelope = {
            "analysis_contract": self._ANALYSIS_CONTRACT,
            "audit_procedure_report": json.loads(report.to_json(indent=2)),
        }

        content_text = json.dumps(
            envelope,
            indent=2,
            ensure_ascii=False,
        )
        content = content_text.encode()
        inline_size = len(content)

        if inline_size > self._max_inline_bytes:
            raise AuditReportAIHandoffError(
                "The completed audit report is too large for the current "
                "direct-evidence AI analysis limit. Nothing was truncated or "
                "silently omitted. Use a smaller result set or wait for the "
                "large-report/batched AI analysis workflow. "
                f"Report size: {inline_size:,} bytes; "
                f"current limit: {self._max_inline_bytes:,} bytes."
            )

        evidence_sha256 = hashlib.sha256(content).hexdigest()

        prompt = self._build_prompt(
            report=report,
            evidence_text=content_text,
            evidence_sha256=evidence_sha256,
        )

        return AuditReportAIPackage(
            filename=filename,
            content=content,
            prompt=prompt,
            report_fingerprint=report.report_fingerprint,
            exception_count=report.summary.exception_count,
            evidence_sha256=evidence_sha256,
            inline_evidence_bytes=inline_size,
        )

    @staticmethod
    def _build_prompt(
        *,
        report: AuditProcedureReport,
        evidence_text: str,
        evidence_sha256: str,
    ) -> str:
        """Return the evidence-grounded audit analysis instruction."""

        return (
            "Analyse the completed audit procedure report using the mandatory "
            "analysis_contract supplied below.\n\n"
            "IMPORTANT EVIDENCE DELIVERY RULE\n"
            "The complete authoritative audit report JSON is embedded directly "
            "in this message below. Analyse that embedded JSON directly. Do not "
            "depend on file retrieval, document search, RAG retrieval, tools or "
            "the presence of a Sources indicator to obtain the audit evidence. "
            "The separately attached JSON file is retained for traceability and "
            "must represent the same evidence.\n\n"
            "AUDIT BOUNDARY\n"
            "The deterministic audit procedure, not the AI, determines which "
            "records are exceptions. An exception means only that the record met "
            "the configured audit-test criteria.\n\n"
            "Do not describe an exception as fraud, error, non-compliance, a "
            "control failure, a misstatement or a confirmed audit finding unless "
            "the supplied report explicitly establishes that conclusion. Do not "
            "convert the exception rate into a non-compliance rate, error rate, "
            "fraud rate, control-failure rate or misstatement rate.\n\n"
            "Do not describe a rate, count, pattern or concentration as high, low, "
            "significant, unusual or acceptable unless the supplied report contains "
            "a benchmark or other evidence supporting that assessment.\n\n"
            "EVIDENCE DISCIPLINE\n"
            "Use only fields and records contained in the authoritative JSON below. "
            "Do not invent classifications or facts. If you create a grouping from "
            "text values, identify the exact field, the matching terms or grouping "
            "rule, and the supporting source-row references.\n\n"
            "For every numerical pattern derived from exception records, state:\n"
            "- Evidence status: DERIVED PATTERN\n"
            "- Numerator\n"
            "- Denominator\n"
            "- Field or fields used\n"
            "- Calculation or grouping rule\n"
            "- Supporting source-row references where available\n\n"
            "Do not repeat the same derived pattern more than once. If those items "
            "cannot be supported from the supplied report, do not present the "
            "pattern as established. State: "
            '"Not established by the supplied audit report."\n\n'
            "Do not ask management what corrective action will be taken unless the "
            "supplied evidence first establishes a condition requiring correction.\n\n"
            "REQUIRED RESPONSE STRUCTURE\n"
            "1. FACTS ESTABLISHED BY THE AUDIT REPORT\n"
            "   Label each item REPORT FACT. Include only facts explicitly present "
            "in the report.\n\n"
            "2. EVIDENCE-SUPPORTED PATTERNS\n"
            "   Label each item DERIVED PATTERN and provide the numerical and "
            "source-row evidence required above.\n\n"
            "3. POSSIBLE EXPLANATIONS\n"
            "   Label each item HYPOTHESIS. Do not present possible causes as facts.\n\n"
            "4. ADDITIONAL EVIDENCE REQUIRED\n"
            "   State what evidence would confirm or reject the important "
            "hypotheses or possible control concerns.\n\n"
            "5. FOLLOW-UP AUDIT PROCEDURES\n"
            "   Recommend focused procedures that follow from the supplied evidence.\n\n"
            "6. QUESTIONS FOR MANAGEMENT\n"
            "   Provide neutral, evidence-led questions and avoid assuming causes, "
            "wrongdoing or the need for corrective action.\n\n"
            "7. MATTERS NOT ESTABLISHED\n"
            "   Explicitly address whether the report establishes fraud, "
            "non-compliance, error, control failure and financial misstatement. "
            "Use NOT ESTABLISHED where the report does not prove the matter.\n\n"
            "Possible explanations must remain hypotheses requiring corroboration. "
            "Auditor judgement and corroboration remain required.\n\n"
            f"Procedure: {report.identity.display_id} — "
            f"{report.identity.name}\n"
            f"Report fingerprint: {report.report_fingerprint}\n"
            f"Authoritative evidence SHA-256: {evidence_sha256}\n"
            f"Population: {report.summary.population_count:,}\n"
            f"Records evaluated: "
            f"{report.summary.records_evaluated_count:,}\n"
            f"Exceptions: {report.summary.exception_count:,}\n"
            f"Exception rate: {report.summary.exception_rate:.2f}%\n\n"
            "BEGIN AUTHORITATIVE AUDIT REPORT JSON\n"
            f"{evidence_text}\n"
            "END AUTHORITATIVE AUDIT REPORT JSON"
        )


class AuditReportAIHandoffService:
    """Send a completed audit report using the user's saved OpenWebUI access."""

    def __init__(
        self,
        *,
        settings_service: OpenWebUISettingsService,
        client: OpenWebUIClient,
        package_builder: AuditReportAIPackageBuilder | None = None,
    ) -> None:
        self._settings_service = settings_service
        self._client = client
        self._package_builder = package_builder or AuditReportAIPackageBuilder()

    def send_report(
        self,
        report: AuditProcedureReport,
    ) -> OpenWebUIAnalysisResult:
        """Upload the report and create a persistent OpenWebUI analysis chat."""

        settings = self._settings_service.get_settings()

        if not settings.enabled:
            raise AuditReportAIHandoffError(
                "OpenWebUI integration is disabled. Enable it under Settings → AI Browser Access."
            )

        if not settings.base_url:
            raise AuditReportAIHandoffError(
                "No OpenWebUI address is configured. Configure it under "
                "Settings → AI Browser Access."
            )

        if not settings.default_model:
            raise AuditReportAIHandoffError(
                "No default OpenWebUI model is selected. Test the connection, "
                "select a model and save the AI Browser Access settings."
            )

        try:
            api_key = self._settings_service.get_api_key(settings.base_url) or ""
        except CredentialStoreError as error:
            raise AuditReportAIHandoffError(
                f"The saved OpenWebUI credential could not be read: {error}"
            ) from error

        if not api_key.strip():
            raise AuditReportAIHandoffError(
                "No saved OpenWebUI API key is available for the configured "
                "address. Save the API key under Settings → AI Browser Access."
            )

        package = self._package_builder.build(report)

        return self._client.analyse_audit_report(
            base_url=settings.base_url,
            api_key=api_key,
            model=settings.default_model,
            title=(f"{report.identity.display_id} — {report.identity.name} | Audit Analysis"),
            filename=package.filename,
            content=package.content,
            prompt=package.prompt,
        )
