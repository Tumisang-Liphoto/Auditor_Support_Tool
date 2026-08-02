"""Shared models used by General Ledger audit tests."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class TestAvailabilityStatus(StrEnum):
    """Technical availability of an audit test."""

    AVAILABLE = "available"
    AVAILABLE_WITH_WARNING = "available_with_warning"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class AuditFieldDefinition:
    """A standard audit field used across different source systems."""

    key: str
    label: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class TestDefinition:
    """Definition and field requirements for one audit test."""

    code: str
    title: str
    category: str
    description: str
    required_fields: tuple[str, ...]
    helpful_fields: tuple[str, ...] = ()
    logic_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """Mapping between a standard field and an uploaded source column."""

    standard_field: str
    source_column: str


@dataclass(frozen=True, slots=True)
class TestAvailability:
    """Result of checking whether a test can run."""

    test_code: str
    status: TestAvailabilityStatus
    mapped_required_fields: tuple[str, ...]
    missing_required_fields: tuple[str, ...]
    mapped_helpful_fields: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def can_run(self) -> bool:
        """Return whether the test is technically executable."""

        return self.status in {
            TestAvailabilityStatus.AVAILABLE,
            TestAvailabilityStatus.AVAILABLE_WITH_WARNING,
        }


@dataclass(frozen=True, slots=True)
class TestMetric:
    """One summary measure produced by an audit test."""

    key: str
    label: str
    value: int | float | str


@dataclass(frozen=True, slots=True)
class TestException:
    """One record identified for further audit scrutiny."""

    exception_id: str
    source_row_number: int
    reason: str
    source_record: dict[str, Any]
    derived_values: dict[str, Any] = field(default_factory=dict)
    group_id: str | None = None


@dataclass(frozen=True, slots=True)
class DataQualityIssue:
    """A source-data issue identified while running a test."""

    issue_type: str
    message: str
    source_row_number: int | None = None
    source_value: Any = None


@dataclass(frozen=True, slots=True)
class TestRunResult:
    """Complete output from one audit-test execution."""

    test_code: str
    test_title: str
    logic_version: str
    source_file: str
    worksheet_name: str
    population_records: int
    records_tested: int
    records_excluded: int
    executed_at: datetime
    metrics: tuple[TestMetric, ...]
    exceptions: tuple[TestException, ...]
    data_quality_issues: tuple[DataQualityIssue, ...] = ()
    configuration: dict[str, Any] = field(default_factory=dict)

    @property
    def exception_count(self) -> int:
        """Return the number of records flagged by the test."""

        return len(self.exceptions)

    def metric_value(self, key: str) -> int | float | str | None:
        """Return a summary metric value by its key."""

        for metric in self.metrics:
            if metric.key == key:
                return metric.value

        return None
