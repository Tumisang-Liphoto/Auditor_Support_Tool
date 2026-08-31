"""Build structured audit procedure reports from authoritative results."""

from __future__ import annotations

from collections.abc import Iterable

from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
)
from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReport,
    AuditProcedureReportException,
    AuditProcedureReportIdentity,
    AuditProcedureReportScope,
    AuditProcedureReportSection,
    AuditProcedureReportSummary,
    normalise_report_mapping,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)


class AuditProcedureReportBuilder:
    """Build provider-neutral reports from deterministic procedure results."""

    def build(
        self,
        *,
        definition: ProcedureDefinition,
        result: ProcedureResult,
        analysis_sections: Iterable[AuditProcedureReportSection] = (),
    ) -> AuditProcedureReport:
        """Return a complete structured report for one procedure run."""

        if definition.procedure_id != result.context.procedure_id:
            raise ValueError("Procedure definition does not match the result procedure identifier.")

        sections = tuple(analysis_sections)

        if not all(isinstance(section, AuditProcedureReportSection) for section in sections):
            raise TypeError("Analysis sections must be AuditProcedureReportSection instances.")

        exceptions = tuple(
            AuditProcedureReportException(
                source_record_id=record.source_record_id,
                source_row_number=record.source_row_number,
                reason_code=record.reason_code,
                reason=record.reason,
                values=normalise_report_mapping(record.values),
                related_value=(
                    str(record.related_value) if record.related_value is not None else None
                ),
            )
            for record in result.exception_records
        )

        context = result.context

        return AuditProcedureReport(
            identity=AuditProcedureReportIdentity(
                procedure_id=definition.procedure_id,
                display_id=definition.display_id,
                name=definition.name,
                category=definition.category,
                description=definition.description,
                procedure_version=context.procedure_version,
            ),
            scope=AuditProcedureReportScope(
                dataset_id=context.dataset_id,
                audit_period_start=context.audit_period_start,
                audit_period_end=context.audit_period_end,
                parameters=normalise_report_mapping(context.parameters),
            ),
            summary=AuditProcedureReportSummary(
                population_count=result.population_count,
                records_evaluated_count=(result.records_evaluated_count),
                excluded_record_count=result.excluded_record_count,
                exception_count=result.exception_count,
                exception_rate=result.exception_rate,
                related_value_total=(
                    str(result.related_value_total)
                    if result.related_value_total is not None
                    else None
                ),
            ),
            exclusion_counts=dict(result.exclusion_counts),
            metrics=normalise_report_mapping(result.metrics),
            limitations=tuple(result.limitations),
            audit_use_statement=result.audit_use_statement,
            exceptions=exceptions,
            analysis_sections=sections,
            execution_id=context.execution_id,
            created_at=context.created_at,
            source_sha256=context.source_sha256,
            mapping_fingerprint=context.mapping_fingerprint,
        )
