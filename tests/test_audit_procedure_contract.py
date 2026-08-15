"""Tests for the standard audit-procedure run/result contract."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    DEFAULT_AUDIT_USE_STATEMENT,
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_run_context_service import (
    AuditRunContextError,
    AuditRunContextService,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
)
from auditor_support_tool.core.source_integrity_service import (
    SourceIntegrityService,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)


def create_prepared_dataset(
    tmp_path: Path,
) -> tuple[Path, PreparedAuditDataset]:
    """Create a small mapped General Ledger dataset."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"

    worksheet.append(
        [
            "Transaction Date",
            "Account Code",
            "Amount",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "1000",
            125.00,
        ]
    )
    worksheet.append(
        [
            "2026-01-05",
            "2000",
            250.00,
        ]
    )

    source_path = tmp_path / "run-context.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    date_column = next(
        column for column in dataset.columns if column.source_column == "Transaction Date"
    )
    account_column = next(
        column for column in dataset.columns if column.source_column == "Account Code"
    )

    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
        account_column.column_id: "account_code",
    }

    return source_path, PreparedAuditDataset(dataset)


def create_context() -> ProcedureRunContext:
    """Create a deterministic valid run context."""

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id="dataset-123",
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        parameters={
            "weekend_days": ["Saturday", "Sunday"],
        },
    )


def test_run_context_copies_execution_identity() -> None:
    """Run context should retain the execution and procedure identity."""

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id="dataset-123",
    )

    parameters = {"weekend_days": ["Saturday", "Sunday"]}

    context = ProcedureRunContext.create(
        request=request,
        procedure_version="1.0.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        parameters=parameters,
    )

    parameters["weekend_days"] = ["Friday"]

    assert context.execution_id == request.execution_id
    assert context.procedure_id == "GL003"
    assert context.dataset_id == "dataset-123"
    assert context.procedure_version == "1.0.0"
    assert context.parameters["weekend_days"] == [
        "Saturday",
        "Sunday",
    ]


def test_run_context_requires_valid_hashes() -> None:
    """Source and mapping fingerprints must be proper SHA-256 digests."""

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id="dataset-123",
    )

    with pytest.raises(
        ValueError,
        match="Source SHA-256",
    ):
        ProcedureRunContext.create(
            request=request,
            procedure_version="1.0.0",
            source_sha256="not-a-hash",
            mapping_fingerprint="b" * 64,
        )


def test_run_context_service_uses_actual_source_hash_and_mapping(
    tmp_path: Path,
) -> None:
    """Context service should capture real source and mapping fingerprints."""

    source_path, prepared_dataset = create_prepared_dataset(tmp_path)

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id=prepared_dataset.dataset_id,
    )

    context = AuditRunContextService().build(
        request=request,
        record_source=prepared_dataset,
        source_path=source_path,
        procedure_version="1.0.0",
        parameters={"weekend_days": [5, 6]},
    )

    assert context.source_sha256 == (SourceIntegrityService().sha256_file(source_path))
    assert context.mapping_fingerprint == (prepared_dataset.mapping_fingerprint)


def test_run_context_rejects_wrong_dataset() -> None:
    """Execution identity and prepared dataset must refer to the same dataset."""

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id="dataset-other",
    )

    class StubPreparedDataset:
        dataset_id = "dataset-123"
        mapping_fingerprint = "b" * 64

    with pytest.raises(
        AuditRunContextError,
        match="does not match",
    ):
        AuditRunContextService().build(
            request=request,
            record_source=StubPreparedDataset(),
            source_path=Path("unused.xlsx"),
            procedure_version="1.0.0",
        )


def test_exception_record_requires_source_link() -> None:
    """Detailed exceptions must retain a stable source-record reference."""

    exception = ProcedureExceptionRecord.create(
        source_record_id="dataset-123:row-17",
        source_row_number=17,
        reason_code="WEEKEND_TRANSACTION",
        reason="Transaction occurred on a configured weekend day.",
        values={
            "transaction_date": "2026-01-03",
            "account_code": "1000",
        },
        related_value=Decimal("125.00"),
    )

    assert exception.source_record_id == "dataset-123:row-17"
    assert exception.source_row_number == 17
    assert exception.related_value == Decimal("125.00")


def test_result_calculates_counts_and_exception_rate() -> None:
    """The standard result should calculate a consistent exception rate."""

    context = create_context()

    exceptions = (
        ProcedureExceptionRecord.create(
            source_record_id="dataset-123:row-2",
            source_row_number=2,
            reason_code="WEEKEND_TRANSACTION",
            reason="Saturday transaction.",
        ),
        ProcedureExceptionRecord.create(
            source_record_id="dataset-123:row-9",
            source_row_number=9,
            reason_code="WEEKEND_TRANSACTION",
            reason="Sunday transaction.",
        ),
    )

    result = ProcedureResult.create(
        context=context,
        population_count=10,
        records_evaluated_count=8,
        exception_records=exceptions,
        exclusion_counts={
            "blank_transaction_date": 1,
            "invalid_transaction_date": 1,
        },
    )

    assert result.population_count == 10
    assert result.records_evaluated_count == 8
    assert result.excluded_record_count == 2
    assert result.exception_count == 2
    assert result.exception_rate == 25.0


def test_result_requires_exclusion_summary_to_reconcile() -> None:
    """Excluded population and reason counts must reconcile exactly."""

    with pytest.raises(
        ValueError,
        match="Exclusion counts",
    ):
        ProcedureResult.create(
            context=create_context(),
            population_count=10,
            records_evaluated_count=8,
            exclusion_counts={
                "blank_transaction_date": 1,
            },
        )


def test_exception_count_cannot_exceed_evaluated_population() -> None:
    """A result cannot report more exceptions than records evaluated."""

    exceptions = tuple(
        ProcedureExceptionRecord.create(
            source_record_id=f"dataset-123:row-{index + 1}",
            source_row_number=index + 1,
            reason_code="TEST",
            reason="Test exception.",
        )
        for index in range(3)
    )

    with pytest.raises(
        ValueError,
        match="Exception count",
    ):
        ProcedureResult.create(
            context=create_context(),
            population_count=3,
            records_evaluated_count=2,
            exception_records=exceptions,
            exclusion_counts={"invalid": 1},
        )


def test_zero_evaluated_records_produces_zero_rate() -> None:
    """A fully excluded population should not create division errors."""

    result = ProcedureResult.create(
        context=create_context(),
        population_count=2,
        records_evaluated_count=0,
        exclusion_counts={
            "invalid_transaction_date": 2,
        },
    )

    assert result.exception_count == 0
    assert result.exception_rate == 0.0


def test_result_preserves_related_value_and_limitations() -> None:
    """Procedure-specific aggregate values and limitations should be retained."""

    result = ProcedureResult.create(
        context=create_context(),
        population_count=5,
        records_evaluated_count=5,
        exclusion_counts={},
        related_value_total=Decimal("5000.25"),
        limitations=("Weekend configuration was supplied by the auditor.",),
        metrics={
            "saturday_count": 2,
            "sunday_count": 1,
        },
    )

    assert result.related_value_total == Decimal("5000.25")
    assert result.limitations == ("Weekend configuration was supplied by the auditor.",)
    assert result.metrics["saturday_count"] == 2
    assert result.audit_use_statement == DEFAULT_AUDIT_USE_STATEMENT
