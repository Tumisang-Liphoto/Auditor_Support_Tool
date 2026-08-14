"""Standard data-quality issue models for audit workspaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4

from auditor_support_tool.core.workspace_models import utc_now_iso


class DataQualitySeverity(StrEnum):
    """Severity assigned to a detected data-quality issue."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class DataQualityScope(StrEnum):
    """Workspace object to which a data-quality issue relates."""

    DATASET = "dataset"
    COLUMN = "column"
    STANDARD_FIELD = "standard_field"


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """One standardised data-quality observation."""

    issue_id: str
    detected_at: str
    code: str
    severity: DataQualitySeverity
    scope: DataQualityScope
    message: str
    dataset_id: str

    column_id: str | None = None
    source_column: str | None = None
    standard_field_key: str | None = None
    affected_record_count: int | None = None
    details: dict[str, object] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        code: str,
        severity: DataQualitySeverity,
        scope: DataQualityScope,
        message: str,
        dataset_id: str,
        column_id: str | None = None,
        source_column: str | None = None,
        standard_field_key: str | None = None,
        affected_record_count: int | None = None,
        details: dict[str, object] | None = None,
    ) -> DataQualityIssue:
        """Create a validated data-quality issue."""

        cleaned_code = code.strip()
        cleaned_message = message.strip()
        cleaned_dataset_id = dataset_id.strip()

        if not cleaned_code:
            raise ValueError("Data-quality issue code is required.")

        if not cleaned_message:
            raise ValueError("Data-quality issue message is required.")

        if not cleaned_dataset_id:
            raise ValueError("Dataset identifier is required.")

        if affected_record_count is not None and affected_record_count < 0:
            raise ValueError("Affected record count cannot be negative.")

        if scope == DataQualityScope.COLUMN and not column_id:
            raise ValueError("Column-scoped data-quality issues require a column identifier.")

        if scope == DataQualityScope.STANDARD_FIELD and not standard_field_key:
            raise ValueError("Standard-field data-quality issues require a standard field key.")

        return cls(
            issue_id=str(uuid4()),
            detected_at=utc_now_iso(),
            code=cleaned_code,
            severity=severity,
            scope=scope,
            message=cleaned_message,
            dataset_id=cleaned_dataset_id,
            column_id=column_id.strip() if column_id else None,
            source_column=source_column.strip() if source_column else None,
            standard_field_key=(standard_field_key.strip() if standard_field_key else None),
            affected_record_count=affected_record_count,
            details=dict(details or {}),
        )

    @property
    def blocks_execution(self) -> bool:
        """Return whether this issue should prevent an affected test from running."""

        return self.severity == DataQualitySeverity.BLOCKING
