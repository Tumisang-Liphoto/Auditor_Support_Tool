"""Resolve exception evidence from the loaded population without interpreting values."""

from dataclasses import dataclass, replace

from auditor_support_tool.core.audit_procedure_models import ProcedureResult
from auditor_support_tool.core.data_models import SOURCE_ROW_FIELD
from auditor_support_tool.core.prepared_audit_dataset import build_source_record_id
from auditor_support_tool.core.workbook_package import WorksheetDataset
from auditor_support_tool.presentation.result_dashboard_models import (
    DashboardTable,
    DashboardTableColumn,
)


@dataclass(frozen=True, slots=True)
class ExceptionSourceRecords:
    """Source cells keyed by canonical identity; absent keys are unresolved."""

    headers: tuple[str, ...]
    records: dict[tuple[str, int], tuple[object, ...]]


def resolve_exception_sources(
    result: ProcedureResult, datasets: tuple[WorksheetDataset, ...]
) -> ExceptionSourceRecords:
    """Scan the matching population once, retaining only unambiguous exception rows.

    Dataset identity and loaded-byte fingerprint must both match the execution.
    Never use list positions, parse an exception ID, or reopen the source file.
    """
    matches = [d for d in datasets if d.dataset_id == result.context.dataset_id]
    empty = ExceptionSourceRecords((), {})
    if len(matches) != 1:
        return empty
    dataset = matches[0]
    table = dataset.loaded_table
    if not table.source_sha256 or table.source_sha256 != result.context.source_sha256:
        return empty
    wanted = {(e.source_record_id, e.source_row_number) for e in result.exception_records}
    headers = tuple(dict.fromkeys(h for h in table.headers if h != SOURCE_ROW_FIELD))
    records = {}
    seen = set()
    for row in table.rows:
        number = row.get(SOURCE_ROW_FIELD)
        # Loaded source row identities are integers. Malformed identities fail closed.
        if type(number) is not int or number < 1:
            continue
        identity = (build_source_record_id(dataset.dataset_id, number), number)
        if identity not in wanted:
            continue
        if identity in seen:
            records.pop(identity, None)
            continue
        seen.add(identity)
        records[identity] = tuple(row.get(header) for header in headers)
    return ExceptionSourceRecords(headers if records else (), records)


def add_source_columns(table: DashboardTable, sources: ExceptionSourceRecords) -> DashboardTable:
    """Extend existing presenter rows by identity, preserving filters and explanations."""
    columns = {column.key: column for column in table.columns}
    columns.setdefault("reason", DashboardTableColumn("reason", "Reason"))
    columns.setdefault("record_id", DashboardTableColumn("record_id", "Record ID"))
    columns["record_id"] = replace(columns["record_id"], visible_by_default=False)
    if not sources.headers:
        return replace(table, columns=tuple(columns.values()))

    # Keys are independent of labels and cannot collide with presenter fields.
    source_columns = []
    for index, header in enumerate(sources.headers):
        key = f"source:{index}"
        while key in columns:
            key = "source:" + key
        source_columns.append(DashboardTableColumn(key, header, index < 12))
    rows = []
    unresolved = 0
    for row in table.rows:
        values = dict(row.values)
        try:
            identity = (values.get("record_id", ""), int(values.get("source_row", "")))
        except ValueError:
            identity = ("", 0)
        cells = sources.records.get(identity)
        if cells is None:
            unresolved += 1
        else:
            for column, cell in zip(source_columns, cells, strict=True):
                values[column.key] = "" if cell is None else str(cell)
        rows.append(replace(row, values=values))
    ordered = (
        columns.pop("source_row", DashboardTableColumn("source_row", "Source Row")),
        *source_columns,
        columns.pop("reason"),
        *(replace(column, visible_by_default=False) for column in columns.values()),
    )
    note = table.source_note
    if unresolved:
        note += f" Source values unavailable for {unresolved:,} exception rows."
    return replace(table, columns=ordered, rows=tuple(rows), source_note=note)
