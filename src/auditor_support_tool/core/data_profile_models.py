"""Generic source-data profiling models shared across audit domains."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DetectedDataType(StrEnum):
    """Broad data types detected in source columns."""

    BLANK = "blank"
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    """Profile information for one uploaded source column."""

    column_name: str
    position: int
    detected_type: DetectedDataType
    total_records: int
    populated_records: int
    blank_records: int
    distinct_values: int
    duplicate_values: int
    minimum_value: Any = None
    maximum_value: Any = None
    sample_values: tuple[Any, ...] = ()

    @property
    def completeness_percentage(self) -> float:
        """Return the percentage of records containing a value."""

        if self.total_records == 0:
            return 0.0

        return round(
            self.populated_records / self.total_records * 100,
            2,
        )


@dataclass(frozen=True, slots=True)
class DataProfile:
    """Profile of an entire uploaded population."""

    source_file: str
    worksheet_name: str
    record_count: int
    column_count: int
    blank_cell_count: int
    completely_blank_rows_skipped: int
    columns: tuple[ColumnProfile, ...]

    @property
    def columns_with_blanks(self) -> int:
        """Return the number of columns containing blank values."""

        return sum(1 for column in self.columns if column.blank_records > 0)

    @property
    def fully_populated_columns(self) -> int:
        """Return the number of columns with no blank values."""

        return sum(1 for column in self.columns if column.blank_records == 0)
