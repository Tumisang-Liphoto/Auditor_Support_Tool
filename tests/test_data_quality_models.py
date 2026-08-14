"""Tests for standard data-quality issue models."""

import pytest

from auditor_support_tool.core.data_quality_models import (
    DataQualityIssue,
    DataQualityScope,
    DataQualitySeverity,
)


def test_warning_issue_can_be_created() -> None:
    """A normal warning should retain its audit context."""

    issue = DataQualityIssue.create(
        code="BLANK_VALUES",
        severity=DataQualitySeverity.WARNING,
        scope=DataQualityScope.COLUMN,
        message="Transaction Date contains blank values.",
        dataset_id="dataset-123",
        column_id="column-456",
        source_column="Transaction Date",
        affected_record_count=12,
    )

    assert issue.issue_id
    assert issue.detected_at
    assert issue.dataset_id == "dataset-123"
    assert issue.column_id == "column-456"
    assert issue.affected_record_count == 12
    assert not issue.blocks_execution


def test_only_blocking_severity_blocks_execution() -> None:
    """Warnings should not automatically prevent audit procedures."""

    warning = DataQualityIssue.create(
        code="PARTIAL_BLANKS",
        severity=DataQualitySeverity.WARNING,
        scope=DataQualityScope.DATASET,
        message="Some optional values are blank.",
        dataset_id="dataset-123",
    )
    blocking = DataQualityIssue.create(
        code="UNUSABLE_DATE_FIELD",
        severity=DataQualitySeverity.BLOCKING,
        scope=DataQualityScope.STANDARD_FIELD,
        message="The mapped transaction date cannot be interpreted as dates.",
        dataset_id="dataset-123",
        standard_field_key="transaction_date",
    )

    assert not warning.blocks_execution
    assert blocking.blocks_execution


def test_column_scope_requires_column_identifier() -> None:
    """Column-level issues require the stable column identifier."""

    with pytest.raises(
        ValueError,
        match="column identifier",
    ):
        DataQualityIssue.create(
            code="INVALID_VALUES",
            severity=DataQualitySeverity.WARNING,
            scope=DataQualityScope.COLUMN,
            message="The column contains invalid values.",
            dataset_id="dataset-123",
        )


def test_standard_field_scope_requires_field_key() -> None:
    """Mapped-field issues require the standard audit-field key."""

    with pytest.raises(
        ValueError,
        match="standard field key",
    ):
        DataQualityIssue.create(
            code="FIELD_QUALITY",
            severity=DataQualitySeverity.WARNING,
            scope=DataQualityScope.STANDARD_FIELD,
            message="The mapped field contains questionable values.",
            dataset_id="dataset-123",
        )


def test_negative_affected_record_count_is_rejected() -> None:
    """Affected-record counts cannot be negative."""

    with pytest.raises(
        ValueError,
        match="cannot be negative",
    ):
        DataQualityIssue.create(
            code="BLANK_VALUES",
            severity=DataQualitySeverity.WARNING,
            scope=DataQualityScope.DATASET,
            message="Blank values were detected.",
            dataset_id="dataset-123",
            affected_record_count=-1,
        )


def test_details_are_copied() -> None:
    """Caller-owned detail dictionaries should not be stored by reference."""

    details = {"blank_percentage": 3.5}

    issue = DataQualityIssue.create(
        code="BLANK_VALUES",
        severity=DataQualitySeverity.INFO,
        scope=DataQualityScope.DATASET,
        message="A small number of blank values were detected.",
        dataset_id="dataset-123",
        details=details,
    )

    details["blank_percentage"] = 99.0

    assert issue.details["blank_percentage"] == 3.5
