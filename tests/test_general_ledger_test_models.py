"""Tests for shared General Ledger audit-test models."""

from datetime import datetime

from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    TestAvailability as AuditTestAvailability,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    TestAvailabilityStatus as AuditTestAvailabilityStatus,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    TestException as AuditTestException,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    TestMetric as AuditTestMetric,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    TestRunResult as AuditTestRunResult,
)


def test_available_test_can_run() -> None:
    """An available test should be executable."""

    availability = AuditTestAvailability(
        test_code="GL-001",
        status=AuditTestAvailabilityStatus.AVAILABLE,
        mapped_required_fields=("invoice_number",),
        missing_required_fields=(),
        mapped_helpful_fields=("vendor_number",),
    )

    assert availability.can_run is True


def test_unavailable_test_cannot_run() -> None:
    """A test missing required fields should not be executable."""

    availability = AuditTestAvailability(
        test_code="GL-003",
        status=AuditTestAvailabilityStatus.UNAVAILABLE,
        mapped_required_fields=(),
        missing_required_fields=("transaction_date",),
        mapped_helpful_fields=(),
    )

    assert availability.can_run is False


def test_run_result_returns_exception_count_and_metric() -> None:
    """A result should expose common summary information."""

    exception = AuditTestException(
        exception_id="GL-001-0001",
        source_row_number=25,
        reason="Repeated invoice number — further scrutiny required.",
        source_record={
            "Invoice Number": "INV-001",
            "_source_row_number": 25,
        },
        group_id="GL-001-GROUP-001",
    )

    result = AuditTestRunResult(
        test_code="GL-001",
        test_title="Duplicate Invoice Detection",
        logic_version="1.0",
        source_file="sample.xlsx",
        worksheet_name="General_Ledger",
        population_records=2_000,
        records_tested=2_000,
        records_excluded=0,
        executed_at=datetime(2026, 8, 2, 20, 0),
        metrics=(
            AuditTestMetric(
                key="duplicate_groups",
                label="Repeated invoice groups",
                value=4,
            ),
            AuditTestMetric(
                key="flagged_records",
                label="Records flagged",
                value=8,
            ),
        ),
        exceptions=(exception,),
    )

    assert result.exception_count == 1
    assert result.metric_value("duplicate_groups") == 4
    assert result.metric_value("flagged_records") == 8
    assert result.metric_value("missing_metric") is None
