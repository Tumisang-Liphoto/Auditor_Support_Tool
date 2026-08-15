"""Dashboard-oriented analytical tests for GL-003 Weekend Transactions."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureRunContext,
)
from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    weekend_transactions,
)

WeekendTransactionsProcedure = weekend_transactions.WeekendTransactionsProcedure


def _create_rich_source(
    tmp_path: Path,
) -> PreparedAuditDataset:
    """Create a mapped population with fields used by GL-003 analysis."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"

    worksheet.append(
        [
            "Transaction Date",
            "Journal",
            "Description",
            "Debit",
            "Credit",
            "Amount",
            "Entry User",
            "Approval User",
            "Journal Type",
            "Journal Source",
        ]
    )

    rows = (
        (
            "2026-01-02",
            "J001",
            "Friday",
            100,
            0,
            100,
            "User A",
            "User B",
            "System",
            "AP",
        ),
        (
            "2026-01-03",
            "J002",
            "Saturday manual same user",
            1000,
            0,
            1000,
            "Alice",
            "alice",
            "Manual",
            "GL",
        ),
        (
            "2026-01-04",
            "J003",
            "Sunday normal",
            0,
            250,
            -250,
            "Bob",
            "Carol",
            "System",
            "AP",
        ),
        (
            "2026-01-10",
            "J004",
            "Saturday high manual",
            5000,
            0,
            5000,
            "Dave",
            "Erin",
            "MANUAL",
            "GL",
        ),
        (
            "2026-01-11",
            "J005",
            "Sunday high same user",
            0,
            7000,
            -7000,
            "Frank",
            "Frank",
            "Automated",
            "AP",
        ),
    )

    for row in rows:
        worksheet.append(row)

    source_path = tmp_path / "gl003-rich.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    mappings = {
        "Transaction Date": (
            "transaction_date",
            DetectedDataType.DATE,
        ),
        "Journal": (
            "journal_number",
            DetectedDataType.TEXT,
        ),
        "Description": (
            "transaction_description",
            DetectedDataType.TEXT,
        ),
        "Debit": (
            "debit_amount",
            DetectedDataType.DECIMAL,
        ),
        "Credit": (
            "credit_amount",
            DetectedDataType.DECIMAL,
        ),
        "Amount": (
            "transaction_amount",
            DetectedDataType.DECIMAL,
        ),
        "Entry User": (
            "entry_user",
            DetectedDataType.TEXT,
        ),
        "Approval User": (
            "approval_user",
            DetectedDataType.TEXT,
        ),
        "Journal Type": (
            "journal_type",
            DetectedDataType.TEXT,
        ),
        "Journal Source": (
            "journal_source",
            DetectedDataType.TEXT,
        ),
    }

    for source_column, (
        standard_field,
        confirmed_type,
    ) in mappings.items():
        column = next(column for column in dataset.columns if column.source_column == source_column)
        column.confirmed_type = confirmed_type
        dataset.field_mappings[column.column_id] = standard_field

    return PreparedAuditDataset(dataset)


def _create_minimal_source(
    tmp_path: Path,
) -> PreparedAuditDataset:
    """Create a GL population with only the required GL-003 field."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"
    worksheet.append(
        [
            "Transaction Date",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
        ]
    )
    worksheet.append(
        [
            "2026-01-04",
        ]
    )

    source_path = tmp_path / "gl003-minimal.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    date_column = next(
        column for column in dataset.columns if column.source_column == "Transaction Date"
    )
    date_column.confirmed_type = DetectedDataType.DATE
    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
    }

    return PreparedAuditDataset(dataset)


def _context(
    dataset_id: str,
    *,
    parameters: dict[str, object] | None = None,
) -> ProcedureRunContext:
    """Create a deterministic GL-003 procedure context."""

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id=dataset_id,
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
        parameters=parameters,
    )


def test_gl003_builds_weekend_dashboard_metrics(
    tmp_path: Path,
) -> None:
    """Mapped optional fields should produce transparent dashboard metrics."""

    source = _create_rich_source(tmp_path)

    result = WeekendTransactionsProcedure().run(
        context=_context(
            source.dataset_id,
            parameters={
                "high_value_threshold": 4000,
                "manual_journal_values": [
                    "manual",
                ],
            },
        ),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.population_count == 5
    assert result.records_evaluated_count == 5
    assert result.exception_count == 4
    assert result.exception_rate == 80.0

    assert result.metrics["saturday_transactions"] == 2
    assert result.metrics["sunday_transactions"] == 2
    assert result.metrics["weekend_percentage"] == 80.0

    assert result.metrics["saturday_debit_total"] == Decimal("6000")
    assert result.metrics["saturday_credit_total"] == Decimal("0")
    assert result.metrics["sunday_debit_total"] == Decimal("0")
    assert result.metrics["sunday_credit_total"] == Decimal("7250")
    assert result.metrics["weekend_debit_total"] == Decimal("6000")
    assert result.metrics["weekend_credit_total"] == Decimal("7250")

    assert result.metrics["high_value_available"] is True
    assert result.metrics["high_value_weekend_count"] == 2

    assert result.metrics["manual_journal_available"] is True
    assert result.metrics["manual_journal_weekend_count"] == 2

    assert result.metrics["same_preparer_approver_available"] is True
    assert result.metrics["same_preparer_approver_count"] == 2

    assert result.metrics["high_risk_available"] is True
    assert result.metrics["high_risk_weekend_count"] == 3
    assert result.metrics["additional_risk_flag_count"] == 6

    assert result.metrics["evaluated_risk_indicators"] == (
        "high_value",
        "manual_journal",
        "same_preparer_approver",
    )
    assert result.metrics["unavailable_risk_indicators"] == ()


def test_gl003_counts_high_risk_records_once(
    tmp_path: Path,
) -> None:
    """Overlapping indicators should not duplicate the high-risk record count."""

    source = _create_rich_source(tmp_path)

    result = WeekendTransactionsProcedure().run(
        context=_context(
            source.dataset_id,
            parameters={
                "high_value_threshold": 4000,
                "manual_journal_values": "manual",
            },
        ),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    exception_by_journal = {
        exception.values["journal_number"]: exception for exception in result.exception_records
    }

    j002 = exception_by_journal["J002"]
    j003 = exception_by_journal["J003"]
    j004 = exception_by_journal["J004"]
    j005 = exception_by_journal["J005"]

    assert j002.values["risk_indicators"] == (
        "manual_journal",
        "same_preparer_approver",
    )
    assert j002.values["risk_indicator_count"] == 2
    assert j002.values["high_risk"] is True

    assert j003.values["risk_indicators"] == ()
    assert j003.values["high_risk"] is False

    assert j004.values["risk_indicators"] == (
        "high_value",
        "manual_journal",
    )
    assert j005.values["risk_indicators"] == (
        "high_value",
        "same_preparer_approver",
    )

    assert result.metrics["high_risk_weekend_count"] == 3
    assert result.metrics["additional_risk_flag_count"] == 6


def test_gl003_reports_unavailable_optional_analysis(
    tmp_path: Path,
) -> None:
    """Missing optional mappings or parameters must not appear as tested zeros."""

    source = _create_minimal_source(tmp_path)

    result = WeekendTransactionsProcedure().run(
        context=_context(
            source.dataset_id,
        ),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.exception_count == 2

    assert result.metrics["debit_summary_available"] is False
    assert result.metrics["credit_summary_available"] is False

    assert result.metrics["high_value_available"] is False
    assert result.metrics["manual_journal_available"] is False
    assert result.metrics["same_preparer_approver_available"] is False
    assert result.metrics["high_risk_available"] is False

    assert result.metrics["high_risk_weekend_count"] == 0
    assert result.metrics["evaluated_risk_indicators"] == ()
    assert result.metrics["unavailable_risk_indicators"] == (
        "high_value",
        "manual_journal",
        "same_preparer_approver",
    )

    limitation_text = " ".join(result.limitations)

    assert "high-value" in limitation_text
    assert "Manual-journal" in limitation_text
    assert "same-preparer/approver" in limitation_text
