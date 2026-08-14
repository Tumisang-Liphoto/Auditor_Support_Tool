"""Prepared audit-dataset access for audit procedures.

This module is the boundary between auditee-specific source columns and
standard audit fields.  Audit procedures should resolve values through this
layer rather than referring to source column names directly.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from typing import Any

from auditor_support_tool.core.data_models import SOURCE_ROW_FIELD
from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.workbook_package import (
    PreparedColumn,
    WorksheetDataset,
)


class PreparedAuditDatasetError(RuntimeError):
    """Raised when prepared audit data cannot be resolved safely."""


class FieldValueStatus(StrEnum):
    """Status of one standard-field value for one source record."""

    VALID = "valid"
    BLANK = "blank"
    INVALID = "invalid"
    UNMAPPED = "unmapped"


@dataclass(frozen=True, slots=True)
class ResolvedFieldValue:
    """Resolved value for one standard audit field."""

    standard_field_key: str
    status: FieldValueStatus
    value: object | None
    raw_value: object | None

    column_id: str | None = None
    source_column: str | None = None
    confirmed_type: DetectedDataType | None = None
    reason: str = ""

    @property
    def is_usable(self) -> bool:
        """Return whether the value is usable by procedure logic."""

        return self.status == FieldValueStatus.VALID


@dataclass(frozen=True, slots=True)
class PreparedAuditRecord:
    """One source record exposed through standard audit fields."""

    dataset: PreparedAuditDataset
    raw_row: Mapping[str, Any]
    source_row_number: int
    source_record_id: str

    def resolve(
        self,
        standard_field_key: str,
    ) -> ResolvedFieldValue:
        """Resolve one mapped standard field for this source record."""

        return self.dataset.resolve_value(
            self.raw_row,
            standard_field_key,
        )

    def value(
        self,
        standard_field_key: str,
        default: object | None = None,
    ) -> object | None:
        """Return a usable value or the supplied default."""

        resolved = self.resolve(standard_field_key)

        if resolved.is_usable:
            return resolved.value

        return default


class PreparedAuditDataset:
    """Expose a prepared worksheet through standard audit-field mappings."""

    def __init__(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        self._dataset = dataset
        self._field_columns = self._build_field_columns(dataset)
        self._mapping_fingerprint = calculate_mapping_fingerprint(dataset)

    @property
    def dataset(self) -> WorksheetDataset:
        """Return the underlying worksheet dataset."""

        return self._dataset

    @property
    def dataset_id(self) -> str:
        """Return the stable dataset identifier."""

        return self._dataset.dataset_id

    @property
    def record_count(self) -> int:
        """Return the complete loaded population count."""

        return self._dataset.record_count

    @property
    def standard_fields(self) -> tuple[str, ...]:
        """Return mapped standard field keys in deterministic order."""

        return tuple(sorted(self._field_columns))

    @property
    def mapping_fingerprint(self) -> str:
        """Return the deterministic SHA-256 fingerprint of the mapping."""

        return self._mapping_fingerprint

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        """Return whether a standard field is mapped and usable structurally."""

        return standard_field_key.strip() in self._field_columns

    def column_for_field(
        self,
        standard_field_key: str,
    ) -> PreparedColumn | None:
        """Return the prepared column supplying a standard field."""

        return self._field_columns.get(standard_field_key.strip())

    def iter_records(self) -> Iterator[PreparedAuditRecord]:
        """Yield wrappers over all source rows without copying the population."""

        for raw_row in self._dataset.loaded_table.rows:
            source_row_number = self._source_row_number(raw_row)

            yield PreparedAuditRecord(
                dataset=self,
                raw_row=raw_row,
                source_row_number=source_row_number,
                source_record_id=build_source_record_id(
                    self.dataset_id,
                    source_row_number,
                ),
            )

    def resolve_value(
        self,
        raw_row: Mapping[str, Any],
        standard_field_key: str,
    ) -> ResolvedFieldValue:
        """Resolve and interpret one standard field from a source row."""

        cleaned_key = standard_field_key.strip()

        if not cleaned_key:
            raise ValueError("Standard field key is required.")

        column = self._field_columns.get(cleaned_key)

        if column is None:
            return ResolvedFieldValue(
                standard_field_key=cleaned_key,
                status=FieldValueStatus.UNMAPPED,
                value=None,
                raw_value=None,
                reason="The standard field is not mapped in this dataset.",
            )

        if column.source_column not in raw_row:
            return ResolvedFieldValue(
                standard_field_key=cleaned_key,
                status=FieldValueStatus.INVALID,
                value=None,
                raw_value=None,
                column_id=column.column_id,
                source_column=column.source_column,
                confirmed_type=column.confirmed_type,
                reason=("The mapped source column is missing from the source record."),
            )

        raw_value = raw_row[column.source_column]

        if _is_blank_value(raw_value):
            return ResolvedFieldValue(
                standard_field_key=cleaned_key,
                status=FieldValueStatus.BLANK,
                value=None,
                raw_value=raw_value,
                column_id=column.column_id,
                source_column=column.source_column,
                confirmed_type=column.confirmed_type,
                reason="The mapped source value is blank.",
            )

        try:
            converted_value = _convert_value(
                raw_value,
                column.confirmed_type,
            )
        except (TypeError, ValueError, InvalidOperation) as error:
            return ResolvedFieldValue(
                standard_field_key=cleaned_key,
                status=FieldValueStatus.INVALID,
                value=None,
                raw_value=raw_value,
                column_id=column.column_id,
                source_column=column.source_column,
                confirmed_type=column.confirmed_type,
                reason=str(error),
            )

        return ResolvedFieldValue(
            standard_field_key=cleaned_key,
            status=FieldValueStatus.VALID,
            value=converted_value,
            raw_value=raw_value,
            column_id=column.column_id,
            source_column=column.source_column,
            confirmed_type=column.confirmed_type,
        )

    @staticmethod
    def _build_field_columns(
        dataset: WorksheetDataset,
    ) -> dict[str, PreparedColumn]:
        """Validate mappings and build standard-field lookup."""

        field_columns: dict[str, PreparedColumn] = {}

        for column_id, raw_field_key in dataset.field_mappings.items():
            field_key = raw_field_key.strip()

            if not field_key:
                continue

            column = dataset.get_column(column_id)

            if column is None:
                raise PreparedAuditDatasetError(
                    f"Field mapping refers to an unknown prepared column: {column_id}"
                )

            if not column.included:
                raise PreparedAuditDatasetError(
                    f"Field mapping refers to an excluded prepared column: {column.source_column}"
                )

            if field_key in field_columns:
                raise PreparedAuditDatasetError(
                    f"A standard audit field is mapped more than once: {field_key}"
                )

            field_columns[field_key] = column

        return field_columns

    @staticmethod
    def _source_row_number(
        raw_row: Mapping[str, Any],
    ) -> int:
        """Return the stable source row number carried by an imported row."""

        raw_source_row = raw_row.get(SOURCE_ROW_FIELD)

        if isinstance(raw_source_row, bool):
            raise PreparedAuditDatasetError(
                "The source record contains an invalid source row number."
            )

        try:
            source_row_number = int(raw_source_row)
        except (TypeError, ValueError) as error:
            raise PreparedAuditDatasetError(
                "The source record is missing a valid source row number."
            ) from error

        if source_row_number < 1:
            raise PreparedAuditDatasetError(
                "The source record contains an invalid source row number."
            )

        return source_row_number


def build_source_record_id(
    dataset_id: str,
    source_row_number: int,
) -> str:
    """Return a stable source-record identity inside one dataset."""

    cleaned_dataset_id = dataset_id.strip()

    if not cleaned_dataset_id:
        raise ValueError("Dataset identifier is required.")

    if source_row_number < 1:
        raise ValueError("Source row number must be at least 1.")

    return f"{cleaned_dataset_id}:row-{source_row_number}"


def calculate_mapping_fingerprint(
    dataset: WorksheetDataset,
) -> str:
    """Return a deterministic SHA-256 fingerprint of active field mappings."""

    entries: list[dict[str, object]] = []

    for column_id, raw_field_key in dataset.field_mappings.items():
        field_key = raw_field_key.strip()

        if not field_key:
            continue

        column = dataset.get_column(column_id)

        if column is None:
            raise PreparedAuditDatasetError(
                f"Cannot fingerprint a mapping that refers to an unknown column ID: {column_id}"
            )

        entries.append(
            {
                "column_id": column.column_id,
                "standard_field_key": field_key,
                "confirmed_type": column.confirmed_type.value,
                "included": column.included,
            }
        )

    entries.sort(
        key=lambda entry: (
            str(entry["standard_field_key"]),
            str(entry["column_id"]),
        )
    )

    payload = {
        "dataset_id": dataset.dataset_id,
        "mappings": entries,
    }

    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    return sha256(canonical_json.encode("utf-8")).hexdigest()


def _convert_value(
    value: object,
    confirmed_type: DetectedDataType,
) -> object:
    """Interpret a populated source value according to its confirmed type."""

    if confirmed_type == DetectedDataType.TEXT:
        return str(value)

    if confirmed_type == DetectedDataType.INTEGER:
        return _to_integer(value)

    if confirmed_type == DetectedDataType.DECIMAL:
        return _to_decimal(value)

    if confirmed_type == DetectedDataType.DATE:
        return _to_date(value)

    if confirmed_type == DetectedDataType.DATETIME:
        return _to_datetime(value)

    # BLANK and MIXED are preparation/profile classifications rather than
    # reliable conversion targets.  Unknown future types are also preserved
    # rather than silently coercced.
    return value


def _to_integer(
    value: object,
) -> int:
    """Convert a source value to an integer without silent rounding."""

    if isinstance(value, bool):
        raise ValueError("Boolean values cannot be interpreted as integers.")

    if isinstance(value, int):
        return value

    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise ValueError("The value is not a whole number.")

        return int(value)

    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("The value is not a whole number.")

        return int(value)

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")

        if not cleaned:
            raise ValueError("The value is blank.")

        decimal_value = Decimal(cleaned)

        if decimal_value != decimal_value.to_integral_value():
            raise ValueError("The value is not a whole number.")

        return int(decimal_value)

    raise TypeError("The value cannot be interpreted as an integer.")


def _to_decimal(
    value: object,
) -> Decimal:
    """Convert a source value to Decimal for audit-safe numeric analysis."""

    if isinstance(value, bool):
        raise ValueError("Boolean values cannot be interpreted as amounts.")

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")

        if not cleaned:
            raise ValueError("The value is blank.")

        return Decimal(cleaned)

    raise TypeError("The value cannot be interpreted as a decimal number.")


def _to_date(
    value: object,
) -> date:
    """Convert a source value to a date using audit-safe parsing rules."""

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise TypeError("The value cannot be interpreted as a date.")

    cleaned = value.strip()

    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass

    parsed = _parse_unambiguous_day_month_year(cleaned)

    if parsed is not None:
        return parsed

    raise ValueError(
        "The value is not a recognised unambiguous date. "
        "Confirm the source date format before using it in an audit procedure."
    )


def _to_datetime(
    value: object,
) -> datetime:
    """Convert a source value to a datetime using audit-safe parsing rules."""

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime.combine(
            value,
            time.min,
        )

    if not isinstance(value, str):
        raise TypeError("The value cannot be interpreted as a datetime.")

    cleaned = value.strip()

    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        pass

    parsed_date = _parse_unambiguous_day_month_year(cleaned)

    if parsed_date is not None:
        return datetime.combine(
            parsed_date,
            time.min,
        )

    raise ValueError("The value is not a recognised unambiguous datetime.")


def _parse_unambiguous_day_month_year(
    value: str,
) -> date | None:
    """Parse slash/dash dates only where day/month order is unambiguous."""

    for separator in ("/", "-"):
        parts = value.split(separator)

        if len(parts) != 3:
            continue

        try:
            first = int(parts[0])
            second = int(parts[1])
            year = int(parts[2])
        except ValueError:
            continue

        if len(parts[2]) != 4:
            continue

        if first > 12 and 1 <= second <= 12:
            return date(
                year,
                second,
                first,
            )

        if second > 12 and 1 <= first <= 12:
            return date(
                year,
                first,
                second,
            )

    return None


def _is_blank_value(
    value: object,
) -> bool:
    """Return whether a source value is blank."""

    if value is None:
        return True

    return isinstance(value, str) and not value.strip()
