"""Detached, procedure-neutral projection of all deterministic exceptions."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from auditor_support_tool.core.audit_procedure_models import ProcedureResult
from auditor_support_tool.core.audit_procedure_report_models import normalise_report_value
from auditor_support_tool.presentation.exception_source_records import ExceptionSourceRecords

Cell = str | int | float | bool | Decimal | None


@dataclass(frozen=True, slots=True)
class ExceptionExportTable:
    headers: tuple[str, ...]
    rows: tuple[tuple[Cell, ...], ...]
    metadata: tuple[tuple[str, Cell], ...]


def _cell(value: object) -> Cell:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite numbers cannot be exported.")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite decimals cannot be exported.")
        return value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    return json.dumps(
        normalise_report_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def build_exception_export_table(
    result: ProcedureResult, sources: ExceptionSourceRecords | None = None
) -> ExceptionExportTable:
    """Retain all rows and all values; no presenter or UI state is consulted."""
    keys = tuple(dict.fromkeys(key for row in result.exception_records for key in row.values))
    if any(not isinstance(key, str) for key in keys):
        raise TypeError("Exception field names must be strings.")
    headers = (
        (
            "dataset_id",
            "source_record_id",
            "source_row_number",
            "procedure_id",
            "procedure_version",
            "execution_id",
        )
        + tuple("value." + key for key in keys)
        + ("reason_code", "reason", "related_value", "source_sha256", "mapping_fingerprint")
    )
    ctx = result.context
    rows = tuple(
        tuple(
            _cell(value)
            for value in (
                ctx.dataset_id,
                row.source_record_id,
                row.source_row_number,
                ctx.procedure_id,
                ctx.procedure_version,
                ctx.execution_id,
                *(row.values.get(key) for key in keys),
                row.reason_code,
                row.reason,
                row.related_value,
                ctx.source_sha256,
                ctx.mapping_fingerprint,
            )
        )
        for row in result.exception_records
    )
    metadata = (
        ("export_scope", "All Exceptions"),
        ("exception_count", result.exception_count),
        ("procedure_id", ctx.procedure_id),
        ("procedure_version", ctx.procedure_version),
        ("dataset_id", ctx.dataset_id),
        ("execution_id", ctx.execution_id),
        ("created_at", ctx.created_at),
        ("source_sha256", ctx.source_sha256),
        ("mapping_fingerprint", ctx.mapping_fingerprint),
        ("audit_period_start", ctx.audit_period_start),
        ("audit_period_end", ctx.audit_period_end),
        ("scope_note", "Search, filters, pagination and hidden columns do not affect this export."),
        (
            "fidelity_note",
            "Identifiers and numbers are stored as text in XLSX; nested values use JSON. "
            "CSV prefixes formula-like strings with an apostrophe; "
            "numeric negatives are unchanged. "
            "CSV is not a byte-perfect copy of source cells.",
        ),
    )
    if sources is not None and sources.headers:
        headers += tuple("source." + header for header in sources.headers)
        rows = tuple(
            values
            + tuple(
                _cell(cell)
                for cell in sources.records.get(
                    (exception.source_record_id, exception.source_row_number),
                    (None,) * len(sources.headers),
                )
            )
            for values, exception in zip(rows, result.exception_records, strict=True)
        )
    return ExceptionExportTable(headers, rows, metadata)
