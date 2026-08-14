"""Generic data profiling service for loaded audit populations."""

from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from numbers import Integral, Real
from typing import Any

from auditor_support_tool.core.data_models import (
    LoadedTable,
)
from auditor_support_tool.core.data_profile_models import (
    ColumnProfile,
    DataProfile,
    DetectedDataType,
)


class DataProfileService:
    """Analyse the structure and quality of an uploaded population."""

    def profile(
        self,
        table: LoadedTable,
        *,
        sample_limit: int = 5,
    ) -> DataProfile:
        """Create a profile for every source column in a loaded table."""

        if sample_limit < 1:
            raise ValueError("The sample-value limit must be at least 1.")

        column_profiles = tuple(
            self._profile_column(
                table,
                column_name=column_name,
                position=position,
                sample_limit=sample_limit,
            )
            for position, column_name in enumerate(
                table.headers,
                start=1,
            )
        )

        return DataProfile(
            source_file=table.source_path.name,
            worksheet_name=table.worksheet_name,
            record_count=table.record_count,
            column_count=table.column_count,
            blank_cell_count=table.summary.blank_cell_count,
            completely_blank_rows_skipped=(table.summary.blank_rows_skipped),
            columns=column_profiles,
        )

    def _profile_column(
        self,
        table: LoadedTable,
        *,
        column_name: str,
        position: int,
        sample_limit: int,
    ) -> ColumnProfile:
        values = tuple(record.get(column_name) for record in table.rows)

        populated_values = tuple(value for value in values if not self._is_blank_value(value))

        blank_records = len(values) - len(populated_values)

        distinct_keys = {self._comparison_key(value) for value in populated_values}

        duplicate_values = self._duplicate_value_count(populated_values)

        detected_type = self._detect_column_type(populated_values)

        minimum_value, maximum_value = self._minimum_and_maximum(
            populated_values,
            detected_type,
        )

        sample_values = self._sample_distinct_values(
            populated_values,
            limit=sample_limit,
        )

        return ColumnProfile(
            column_name=column_name,
            position=position,
            detected_type=detected_type,
            total_records=len(values),
            populated_records=len(populated_values),
            blank_records=blank_records,
            distinct_values=len(distinct_keys),
            duplicate_values=duplicate_values,
            minimum_value=minimum_value,
            maximum_value=maximum_value,
            sample_values=sample_values,
        )

    def _detect_column_type(
        self,
        values: tuple[Any, ...],
    ) -> DetectedDataType:
        if not values:
            return DetectedDataType.BLANK

        detected_types = {self._detect_value_type(value) for value in values}

        if detected_types == {
            DetectedDataType.INTEGER,
            DetectedDataType.DECIMAL,
        }:
            return DetectedDataType.DECIMAL

        if detected_types == {
            DetectedDataType.DATE,
            DetectedDataType.DATETIME,
        }:
            return DetectedDataType.DATETIME

        if len(detected_types) == 1:
            return next(iter(detected_types))

        return DetectedDataType.MIXED

    @staticmethod
    def _detect_value_type(
        value: Any,
    ) -> DetectedDataType:
        if isinstance(value, bool):
            return DetectedDataType.BOOLEAN

        if isinstance(value, datetime):
            return DetectedDataType.DATETIME

        if isinstance(value, date):
            return DetectedDataType.DATE

        if isinstance(value, Integral):
            return DetectedDataType.INTEGER

        if isinstance(value, (Real, Decimal)):
            return DetectedDataType.DECIMAL

        return DetectedDataType.TEXT

    def _duplicate_value_count(
        self,
        values: tuple[Any, ...],
    ) -> int:
        counts = Counter(self._comparison_key(value) for value in values)

        return sum(count - 1 for count in counts.values() if count > 1)

    def _sample_distinct_values(
        self,
        values: tuple[Any, ...],
        *,
        limit: int,
    ) -> tuple[Any, ...]:
        samples: list[Any] = []
        seen: set[tuple[str, str]] = set()

        for value in values:
            key = self._comparison_key(value)

            if key in seen:
                continue

            seen.add(key)
            samples.append(value)

            if len(samples) >= limit:
                break

        return tuple(samples)

    def _minimum_and_maximum(
        self,
        values: tuple[Any, ...],
        detected_type: DetectedDataType,
    ) -> tuple[Any, Any]:
        if not values:
            return None, None

        if detected_type not in {
            DetectedDataType.INTEGER,
            DetectedDataType.DECIMAL,
            DetectedDataType.DATE,
            DetectedDataType.DATETIME,
        }:
            return None, None

        try:
            return min(values), max(values)
        except TypeError:
            return None, None

    @staticmethod
    def _comparison_key(
        value: Any,
    ) -> tuple[str, str]:
        """Return a stable key for distinct and duplicate calculations."""

        if isinstance(value, str):
            return (
                "text",
                value.strip().casefold(),
            )

        if isinstance(value, datetime):
            return (
                "datetime",
                value.isoformat(),
            )

        if isinstance(value, date):
            return (
                "date",
                value.isoformat(),
            )

        return (
            type(value).__name__,
            str(value),
        )

    @staticmethod
    def _is_blank_value(
        value: Any,
    ) -> bool:
        if value is None:
            return True

        return isinstance(value, str) and not value.strip()
