"""One complete presentation of authoritative report evidence for every export format."""

from dataclasses import dataclass
from itertools import chain

from auditor_support_tool.core.audit_procedure_models import ProcedureResult
from auditor_support_tool.core.audit_procedure_report_builder import AuditProcedureReportBuilder
from auditor_support_tool.core.audit_procedure_report_models import AuditProcedureReport
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.presentation.audit_procedure_report_formatter import report_display_label
from auditor_support_tool.presentation.exception_export_table import Cell, _cell
from auditor_support_tool.presentation.exception_source_records import ExceptionSourceRecords
from auditor_support_tool.presentation.result_presenter_registry import present_result


@dataclass(frozen=True, slots=True)
class ReportExportRequest:
    """Captured run and supplementary context; the worker takes a detached copy."""

    definition: ProcedureDefinition
    result: ProcedureResult
    sources: ExceptionSourceRecords | None
    workspace_name: str = ""
    auditee_name: str = ""
    dataset_name: str = ""
    worksheet_name: str = ""


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    paragraphs: tuple[str, ...] = ()
    rows: tuple[tuple[str, Cell], ...] = ()


@dataclass(frozen=True, slots=True)
class ReportDocument:
    report: AuditProcedureReport
    sections: tuple[ReportSection, ...]
    exception_headers: tuple[str, ...]
    exception_rows: tuple[tuple[Cell, ...], ...]
    evidence: ReportSection

    def exception_bands(self):
        """Repeat both identities in each readable group; include every field and row."""
        for start in range(2, len(self.exception_headers), 3):
            indices = (0, 1, *range(start, min(start + 3, len(self.exception_headers))))
            yield (
                tuple(self.exception_headers[i] for i in indices),
                tuple(tuple(row[i] for i in indices) for row in self.exception_rows),
            )


def _pairs(value: object, prefix: str = "") -> list[tuple[str, Cell]]:
    """Display nested deterministic metrics/parameters without Python object reprs."""
    if isinstance(value, (dict, list, tuple)) and not value:
        return [(prefix, _cell(value))]
    if isinstance(value, dict):
        return [
            pair
            for key, item in value.items()
            for pair in _pairs(item, f"{prefix} / {report_display_label(key)}".strip(" /"))
        ]
    if isinstance(value, (list, tuple)):
        return [
            pair
            for index, item in enumerate(value, 1)
            for pair in _pairs(item, f"{prefix} / {index}")
        ]
    return [(prefix, _cell(value))]


def build_report_document(request: ReportExportRequest) -> ReportDocument:
    """Use all result exceptions; refuse incomplete or mismatched source evidence."""
    result = request.result
    report = AuditProcedureReportBuilder().build(definition=request.definition, result=result)
    if len(report.exceptions) != report.summary.exception_count:
        raise ValueError("The report exception count does not match its evidence.")
    sources = request.sources
    if report.exceptions and (
        sources is None
        or sources.dataset_id != report.scope.dataset_id
        or sources.source_sha256 != report.source_sha256
        or not sources.headers
        or any(
            (e.source_record_id, e.source_row_number) not in sources.records
            for e in report.exceptions
        )
    ):
        raise ValueError(
            "Complete source transaction evidence is unavailable. "
            "Refresh the source and rerun the procedure before exporting the report."
        )
    headers = sources.headers if sources is not None else ()
    rows = []
    for exception in report.exceptions:
        cells = sources.records[(exception.source_record_id, exception.source_row_number)]
        if len(cells) != len(headers):
            raise ValueError("Source transaction columns do not match the evidence.")
        rows.append(
            tuple(
                _cell(value)
                for value in (
                    exception.source_row_number,
                    exception.source_record_id,
                    *cells,
                    exception.reason,
                    exception.reason_code,
                    exception.values,
                    exception.related_value,
                )
            )
        )
    presentation = present_result(procedure_id=report.identity.procedure_id, result=result)
    summary = report.summary
    period = " to ".join(
        filter(None, (report.scope.audit_period_start, report.scope.audit_period_end))
    )
    sections = [
        ReportSection(
            "Report context",
            rows=(
                ("Procedure", f"{report.identity.display_id} - {report.identity.name}"),
                ("Audit / workspace", request.workspace_name or "Not recorded"),
                ("Auditee", request.auditee_name or "Not recorded"),
                ("Audit period", period or "Not specified"),
                ("Executed", report.created_at),
                ("Dataset", request.dataset_name or report.scope.dataset_id),
                ("Worksheet", request.worksheet_name or "Not recorded"),
                ("Procedure version", report.identity.procedure_version),
            ),
        ),
        ReportSection("Procedure purpose", (report.identity.description,)),
        ReportSection(
            "Result summary",
            rows=(
                ("Population", summary.population_count),
                ("Evaluated", summary.records_evaluated_count),
                ("Excluded", summary.excluded_record_count),
                ("Exceptions", summary.exception_count),
                ("Exception rate (%)", summary.exception_rate),
                ("Related value total", summary.related_value_total),
            ),
        ),
        ReportSection("Procedure metrics", rows=tuple(_pairs(report.metrics))),
        ReportSection("Key observations", presentation.observations),
        ReportSection("Areas requiring attention", presentation.attention_areas),
        ReportSection(
            "Interpretation and limitations", (report.audit_use_statement, *report.limitations)
        ),
    ]
    if report.exclusion_counts:
        sections.append(ReportSection("Exclusions", rows=tuple(_pairs(report.exclusion_counts))))
    for section in report.analysis_sections:
        sections.append(
            ReportSection(
                section.title,
                (section.narrative,) if section.narrative else (),
                tuple(_pairs(section.data)) if section.data else (),
            )
        )
    evidence = ReportSection(
        "Execution evidence",
        rows=(
            ("Execution ID", report.execution_id),
            ("Procedure ID", report.identity.procedure_id),
            ("Procedure version", report.identity.procedure_version),
            ("Dataset ID", report.scope.dataset_id),
            ("Source SHA-256", report.source_sha256),
            ("Mapping fingerprint", report.mapping_fingerprint),
            ("Audit period start", report.scope.audit_period_start),
            ("Audit period end", report.scope.audit_period_end),
            ("Execution timestamp", report.created_at),
            ("Structured report fingerprint", report.report_fingerprint),
            ("Parameters", _cell(report.scope.parameters)),
        ),
        paragraphs=(
            "The structured report fingerprint covers the authoritative report. "
            "Workspace labels and resolved source cells are supplementary presentation evidence; "
            "source cells are linked by dataset, source hash, record ID and source row.",
        ),
    )
    document = ReportDocument(
        report,
        tuple(sections),
        ("Source Row", "Record ID", *headers, "Reason", "Reason code", "Details", "Related value"),
        tuple(rows),
        evidence,
    )

    for value in chain(
        (cell for row in document.exception_rows for cell in row),
        document.exception_headers,
        (
            value
            for section in (*document.sections, document.evidence)
            for value in chain(
                (section.title,), section.paragraphs, (cell for row in section.rows for cell in row)
            )
        ),
    ):
        if isinstance(value, str):
            value.encode("utf-8")
            if any(
                (ord(c) < 32 and c not in "\t\n\r") or ord(c) in (0xFFFE, 0xFFFF) for c in value
            ):
                raise ValueError("Report text contains unsupported control characters.")
    return document
