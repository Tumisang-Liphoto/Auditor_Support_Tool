"""Structured, provider-neutral audit procedure report models.

The report is the stable boundary between deterministic audit-procedure
execution and later presentation/export/AI integrations. It contains only
facts produced by the procedure result plus optional domain-supplied report
sections.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path

REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class AuditProcedureReportIdentity:
    """Procedure identity recorded in an audit procedure report."""

    procedure_id: str
    display_id: str
    name: str
    category: str
    description: str
    procedure_version: str


@dataclass(frozen=True, slots=True)
class AuditProcedureReportScope:
    """Execution scope and configuration used by the procedure."""

    dataset_id: str
    audit_period_start: str
    audit_period_end: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class AuditProcedureReportSummary:
    """Headline result counts and values."""

    population_count: int
    records_evaluated_count: int
    excluded_record_count: int
    exception_count: int
    exception_rate: float
    related_value_total: str | None


@dataclass(frozen=True, slots=True)
class AuditProcedureReportException:
    """One source-linked exception included in the report."""

    source_record_id: str
    source_row_number: int
    reason_code: str
    reason: str
    values: dict[str, object]
    related_value: str | None


@dataclass(frozen=True, slots=True)
class AuditProcedureReportSection:
    """Optional domain-supplied narrative or structured report section.

    Core does not interpret section meaning. A procedure-specific presenter
    may later add sections such as duplicate-group analysis or self-approval
    concentration without teaching core those audit concepts.
    """

    title: str
    narrative: str = ""
    data: dict[str, object] | None = None

    @classmethod
    def create(
        cls,
        *,
        title: str,
        narrative: str = "",
        data: Mapping[str, object] | None = None,
    ) -> AuditProcedureReportSection:
        """Create one validated report section."""

        cleaned_title = title.strip()

        if not cleaned_title:
            raise ValueError("Report section title is required.")

        return cls(
            title=cleaned_title,
            narrative=narrative.strip(),
            data=(normalise_report_mapping(data) if data is not None else None),
        )


@dataclass(frozen=True, slots=True)
class AuditProcedureReport:
    """Complete structured report for one deterministic procedure run."""

    identity: AuditProcedureReportIdentity
    scope: AuditProcedureReportScope
    summary: AuditProcedureReportSummary

    exclusion_counts: dict[str, int]
    metrics: dict[str, object]
    limitations: tuple[str, ...]
    audit_use_statement: str
    exceptions: tuple[AuditProcedureReportException, ...]
    analysis_sections: tuple[AuditProcedureReportSection, ...]

    execution_id: str
    created_at: str
    source_sha256: str
    mapping_fingerprint: str

    schema_version: int = REPORT_SCHEMA_VERSION

    @property
    def report_fingerprint(self) -> str:
        """Return deterministic SHA-256 identity for report audit content.

        Volatile execution metadata (execution ID and creation timestamp) is
        deliberately excluded. Two executions that produce the same report
        from the same source/mapping therefore have the same report
        fingerprint, while the individual run remains traceable through
        ``execution_id`` and ``created_at``.
        """

        payload = self.to_dict(include_fingerprint=False)

        reproducibility = dict(payload["reproducibility"])
        reproducibility.pop("execution_id", None)
        reproducibility.pop("created_at", None)
        payload["reproducibility"] = reproducibility

        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        return hashlib.sha256(encoded).hexdigest()

    def to_dict(
        self,
        *,
        include_fingerprint: bool = True,
    ) -> dict[str, object]:
        """Return a JSON-safe representation for export or AI packaging."""

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "identity": {
                "procedure_id": self.identity.procedure_id,
                "display_id": self.identity.display_id,
                "name": self.identity.name,
                "category": self.identity.category,
                "description": self.identity.description,
                "procedure_version": self.identity.procedure_version,
            },
            "scope": {
                "dataset_id": self.scope.dataset_id,
                "audit_period_start": self.scope.audit_period_start,
                "audit_period_end": self.scope.audit_period_end,
                "parameters": normalise_report_mapping(self.scope.parameters),
            },
            "summary": {
                "population_count": self.summary.population_count,
                "records_evaluated_count": (self.summary.records_evaluated_count),
                "excluded_record_count": (self.summary.excluded_record_count),
                "exception_count": self.summary.exception_count,
                "exception_rate": self.summary.exception_rate,
                "related_value_total": (self.summary.related_value_total),
            },
            "exclusion_counts": dict(self.exclusion_counts),
            "metrics": normalise_report_mapping(self.metrics),
            "limitations": list(self.limitations),
            "audit_use_statement": self.audit_use_statement,
            "exceptions": [
                {
                    "source_record_id": exception.source_record_id,
                    "source_row_number": exception.source_row_number,
                    "reason_code": exception.reason_code,
                    "reason": exception.reason,
                    "values": normalise_report_mapping(exception.values),
                    "related_value": exception.related_value,
                }
                for exception in self.exceptions
            ],
            "analysis_sections": [
                {
                    "title": section.title,
                    "narrative": section.narrative,
                    "data": (
                        normalise_report_mapping(section.data) if section.data is not None else None
                    ),
                }
                for section in self.analysis_sections
            ],
            "reproducibility": {
                "execution_id": self.execution_id,
                "created_at": self.created_at,
                "source_sha256": self.source_sha256,
                "mapping_fingerprint": self.mapping_fingerprint,
            },
        }

        if include_fingerprint:
            payload["report_fingerprint"] = self.report_fingerprint

        return payload

    def to_json(
        self,
        *,
        indent: int = 2,
    ) -> str:
        """Return the complete report as JSON."""

        return json.dumps(
            self.to_dict(),
            indent=indent,
            ensure_ascii=False,
        )


def normalise_report_mapping(
    values: Mapping[str, object],
) -> dict[str, object]:
    """Return a detached JSON-safe copy of a report mapping."""

    return {str(key): normalise_report_value(value) for key, value in values.items()}


def normalise_report_value(
    value: object,
) -> object:
    """Convert supported procedure values into stable JSON-safe values."""

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, Enum):
        return normalise_report_value(value.value)

    if isinstance(value, Mapping):
        return normalise_report_mapping(value)

    if isinstance(value, (list, tuple)):
        return [normalise_report_value(item) for item in value]

    if isinstance(value, (set, frozenset)):
        normalised = [normalise_report_value(item) for item in value]

        return sorted(
            normalised,
            key=lambda item: json.dumps(
                item,
                sort_keys=True,
                ensure_ascii=False,
            ),
        )

    if is_dataclass(value):
        return normalise_report_value(asdict(value))

    raise TypeError(f"Unsupported audit procedure report value type: {type(value).__name__}.")
