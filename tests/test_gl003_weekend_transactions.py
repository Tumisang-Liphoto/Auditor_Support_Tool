"""Tests for the GL-003 Weekend Transactions procedure."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionCancelledError,
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
from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineStatus as EngineStatus,
)
from auditor_support_tool.core.test_engine_service import (
    TestEngineService as EngineService,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    weekend_transactions,
)

WeekendTransactionsProcedure = weekend_transactions.WeekendTransactionsProcedure


def create_prepared_source(
    tmp_path: Path,
) -> tuple[Path, PreparedAuditDataset]:
    """Create a representative mapped population for GL-003."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Audit_Data"

    worksheet.append(
        [
            "Posting Date",
            "Journal Reference",
            "Narrative",
        ]
    )
    worksheet.append(
        [
            "2026-01-02",
            "J001",
            "Friday transaction",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "J002",
            "Saturday transaction",
        ]
    )
    worksheet.append(
        [
            "2026-01-04",
            "J003",
            "Sunday transaction",
        ]
    )
    worksheet.append(
        [
            "2026-01-05",
            "J004",
            "Monday transaction",
        ]
    )
    worksheet.append(
        [
            None,
            "J005",
            "Blank date",
        ]
    )
    worksheet.append(
        [
            "not-a-date",
            "J006",
            "Invalid date",
        ]
    )
    worksheet.append(
        [
            "2025-12-27",
            "J007",
            "Out-of-period Saturday",
        ]
    )

    source_path = tmp_path / "gl003.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("Audit_Data")

    assert dataset is not None

    date_column = next(
        column for column in dataset.columns if column.source_column == "Posting Date"
    )
    reference_column = next(
        column for column in dataset.columns if column.source_column == "Journal Reference"
    )
    narrative_column = next(
        column for column in dataset.columns if column.source_column == "Narrative"
    )

    date_column.confirmed_type = DetectedDataType.DATE
    reference_column.confirmed_type = DetectedDataType.TEXT
    narrative_column.confirmed_type = DetectedDataType.TEXT

    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
        reference_column.column_id: "journal_number",
        narrative_column.column_id: "transaction_description",
    }

    return (
        source_path,
        PreparedAuditDataset(dataset),
    )


def create_context(
    dataset_id: str,
    *,
    audit_period_start: str = "",
    audit_period_end: str = "",
) -> ProcedureRunContext:
    """Create a valid GL-003 run context."""

    request = AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id=dataset_id,
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        audit_period_start=audit_period_start,
        audit_period_end=audit_period_end,
    )


def test_gl003_uses_authoritative_catalogue_definition() -> None:
    """The real procedure should use the catalogue definition."""

    procedure = WeekendTransactionsProcedure()

    assert procedure.definition.procedure_id == "GL003"
    assert procedure.definition.display_id == "GL-003"
    assert procedure.definition.required_fields == ("transaction_date",)


def test_gl003_flags_saturday_and_sunday(
    tmp_path: Path,
) -> None:
    """Weekend dates should produce source-linked exceptions."""

    _source_path, source = create_prepared_source(tmp_path)

    procedure = WeekendTransactionsProcedure()
    context = create_context(
        source.dataset_id,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
    )

    result = procedure.run(
        context=context,
        source=source,
        cancellation_token=(ExecutionCancellationToken()),
    )

    assert result.population_count == 7
    assert result.records_evaluated_count == 4
    assert result.excluded_record_count == 3

    assert result.exception_count == 2
    assert result.exception_rate == 50.0

    assert result.metrics["saturday_transactions"] == 1
    assert result.metrics["sunday_transactions"] == 1
    assert result.metrics["distinct_weekend_dates"] == 2


def test_gl003_exclusions_reconcile(
    tmp_path: Path,
) -> None:
    """Blank, invalid and out-of-period dates should remain accounted for."""

    _source_path, source = create_prepared_source(tmp_path)

    result = WeekendTransactionsProcedure().run(
        context=create_context(
            source.dataset_id,
            audit_period_start="2026-01-01",
            audit_period_end="2026-12-31",
        ),
        source=source,
        cancellation_token=(ExecutionCancellationToken()),
    )

    assert result.exclusion_counts == {
        "blank_transaction_date": 1,
        "invalid_transaction_date": 1,
        "outside_audit_period": 1,
    }

    assert result.records_evaluated_count + result.excluded_record_count == result.population_count


def test_gl003_exception_uses_standard_helpful_fields(
    tmp_path: Path,
) -> None:
    """Mapped helpful fields should flow into exception review automatically."""

    _source_path, source = create_prepared_source(tmp_path)

    result = WeekendTransactionsProcedure().run(
        context=create_context(
            source.dataset_id,
            audit_period_start="2026-01-01",
            audit_period_end="2026-12-31",
        ),
        source=source,
        cancellation_token=(ExecutionCancellationToken()),
    )

    first_exception = result.exception_records[0]

    assert first_exception.source_row_number == 3
    assert first_exception.source_record_id.endswith(":row-3")

    assert first_exception.values["transaction_date"] == "2026-01-03"
    assert first_exception.values["day_of_week"] == "Saturday"
    assert first_exception.values["journal_number"] == "J002"
    assert first_exception.values["transaction_description"] == "Saturday transaction"


def test_gl003_without_period_evaluates_all_usable_dates(
    tmp_path: Path,
) -> None:
    """Older workspaces without a period should still execute transparently."""

    _source_path, source = create_prepared_source(tmp_path)

    result = WeekendTransactionsProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=(ExecutionCancellationToken()),
    )

    assert result.records_evaluated_count == 5
    assert result.exception_count == 3
    assert result.excluded_record_count == 2
    assert len(result.limitations) == 1


def test_gl003_honours_cooperative_cancellation(
    tmp_path: Path,
) -> None:
    """The procedure should stop promptly when cancellation is requested."""

    _source_path, source = create_prepared_source(tmp_path)

    token = ExecutionCancellationToken()
    token.cancel()

    with pytest.raises(AuditExecutionCancelledError):
        WeekendTransactionsProcedure().run(
            context=create_context(source.dataset_id),
            source=source,
            cancellation_token=token,
        )


def test_gl003_runs_through_test_engine(
    tmp_path: Path,
) -> None:
    """GL-003 should complete through the full generic Test Engine pipeline."""

    source_path, source = create_prepared_source(tmp_path)

    registry = ProcedureRegistry()
    registry.register(WeekendTransactionsProcedure())

    engine = EngineService(registry=registry)

    outcome = engine.run(
        procedure_id="GL-003",
        source=source,
        source_path=source_path,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None

    assert outcome.result.exception_count == 2
    assert outcome.result.population_count == 7
    assert outcome.result.context.procedure_id == "GL003"


def test_gl003_transaction_dates_are_resolved_as_dates(
    tmp_path: Path,
) -> None:
    """GL-003 should receive typed dates from the prepared-data boundary."""

    _source_path, source = create_prepared_source(tmp_path)

    first_record = next(source.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.value == date(
        2026,
        1,
        2,
    )
