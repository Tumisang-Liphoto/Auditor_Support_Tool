"""Shared data models for General Ledger audit analytics."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_ROW_FIELD = "_source_row_number"


@dataclass(frozen=True, slots=True)
class WorksheetInfo:
    """Metadata describing one worksheet or CSV data source."""

    name: str
    position: int
    maximum_row: int
    maximum_column: int
    estimated_data_rows: int


@dataclass(frozen=True, slots=True)
class SourceFileInfo:
    """Metadata describing a supported source file."""

    path: Path
    file_type: str
    file_size_bytes: int
    worksheets: tuple[WorksheetInfo, ...]


@dataclass(frozen=True, slots=True)
class HeaderChange:
    """A change made to a blank, duplicate or reserved header."""

    column_number: int
    original_header: str
    resolved_header: str
    reason: str


@dataclass(frozen=True, slots=True)
class PopulationSummary:
    """Basic information about a loaded worksheet population."""

    source_records_read: int
    records_loaded: int
    blank_rows_skipped: int
    column_count: int
    blank_cell_count: int
    header_changes: tuple[HeaderChange, ...]


@dataclass(frozen=True, slots=True)
class LoadedTable:
    """A worksheet or CSV population loaded for audit testing."""

    source_path: Path
    file_type: str
    worksheet_name: str
    headers: tuple[str, ...]
    original_headers: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    summary: PopulationSummary

    @property
    def record_count(self) -> int:
        """Return the number of records available for testing."""

        return len(self.rows)

    @property
    def column_count(self) -> int:
        """Return the number of source-data columns."""

        return len(self.headers)
