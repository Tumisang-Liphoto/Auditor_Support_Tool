"""Tests for GL-006 Segregation of Duties."""

from __future__ import annotations

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
    segregation_of_duties,
)

SegregationOfDutiesProcedure = segregation_of_duties.SegregationOfDutiesProcedure


def create_prepared_source(
    tmp_path: Path,
    *,
    include_helpful_mapping: bool = True,
    extra_rows: tuple[tuple[object, ...], ...] = (),
) -> tuple[Path, PreparedAuditDataset]:
    """Create a representative mapped population for GL-006."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Audit_Data"

    worksheet.append(
        [
            "Entry User",
            "Approval User",
            "Journal",
            "Amount",
            "Account",
            "Narrative",
        ]
    )
    worksheet.append(["Alice", "Alice", "J001", 100, "4000", "Exact match"])
    worksheet.append(["Bob", "bob", "J002", 200, "5000", "Case match"])
    worksheet.append([" Carol ", "carol", "J003", 300, "6000", "Space match"])
    worksheet.append(["Dave", "Eve", "J004", 400, "7000", "Different users"])
    worksheet.append([None, "Frank", "J005", 500, "8000", "Blank entry user"])
    worksheet.append(["Grace", None, "J006", 600, "9000", "Blank approval user"])
    worksheet.append(
        [
            "SYSTEM_BATCH",
            "system_batch",
            "J007",
            700,
            "1000",
            "System account",
        ]
    )

    for row in extra_rows:
        worksheet.append(list(row))

    source_path = tmp_path / "gl006.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("Audit_Data")

    assert dataset is not None

    columns = {column.source_column: column for column in dataset.columns}

    columns["Entry User"].confirmed_type = DetectedDataType.TEXT
    columns["Approval User"].confirmed_type = DetectedDataType.TEXT
    columns["Journal"].confirmed_type = DetectedDataType.TEXT
    columns["Amount"].confirmed_type = DetectedDataType.DECIMAL
    columns["Account"].confirmed_type = DetectedDataType.TEXT
    columns["Narrative"].confirmed_type = DetectedDataType.TEXT

    field_mappings = {
        columns["Entry User"].column_id: "entry_user",
        columns["Approval User"].column_id: "approval_user",
    }

    if include_helpful_mapping:
        field_mappings.update(
            {
                columns["Journal"].column_id: "journal_number",
                columns["Amount"].column_id: "transaction_amount",
                columns["Account"].column_id: "account_code",
                columns["Narrative"].column_id: "transaction_description",
            }
        )

    dataset.field_mappings = field_mappings

    return source_path, PreparedAuditDataset(dataset)


def create_context(dataset_id: str) -> ProcedureRunContext:
    """Create a valid GL-006 run context."""

    request = AuditExecutionRequest.create(
        procedure_id="GL006",
        dataset_id=dataset_id,
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )


def test_gl006_uses_authoritative_catalogue_definition() -> None:
    """The real procedure should use the catalogue definition."""

    procedure = SegregationOfDutiesProcedure()

    assert procedure.definition.procedure_id == "GL006"
    assert procedure.definition.display_id == "GL-006"
    assert procedure.definition.required_fields == (
        "entry_user",
        "approval_user",
    )
    assert procedure.definition.parameter_definitions == ()


def test_gl006_normalises_case_and_surrounding_spaces(tmp_path: Path) -> None:
    """Case and surrounding spaces should not hide same-user exceptions."""

    _source_path, source = create_prepared_source(tmp_path)

    result = SegregationOfDutiesProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.population_count == 7
    assert result.records_evaluated_count == 5
    assert result.exception_count == 4
    assert result.exception_rate == 80.0
    assert result.metrics["distinct_conflicting_users"] == 4

    normalised_users = {record.values["normalised_user"] for record in result.exception_records}

    assert normalised_users == {
        "alice",
        "bob",
        "carol",
        "system_batch",
    }


def test_gl006_blank_users_are_excluded_not_matched(tmp_path: Path) -> None:
    """Blank required user values must not become false self-approval matches."""

    _source_path, source = create_prepared_source(tmp_path)

    result = SegregationOfDutiesProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.exclusion_counts == {
        "blank_entry_user": 1,
        "blank_approval_user": 1,
    }
    assert result.records_evaluated_count + result.excluded_record_count == 7


def test_gl006_retains_source_traceability_and_helpful_fields(tmp_path: Path) -> None:
    """Flagged records should retain mapped context and source identity."""

    _source_path, source = create_prepared_source(tmp_path)

    result = SegregationOfDutiesProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    first_exception = result.exception_records[0]

    assert first_exception.source_row_number == 2
    assert first_exception.source_record_id.endswith(":row-2")
    assert first_exception.reason_code == "SAME_ENTRY_AND_APPROVAL_USER"
    assert first_exception.values["entry_user"] == "Alice"
    assert first_exception.values["approval_user"] == "Alice"
    assert first_exception.values["journal_number"] == "J001"
    assert first_exception.values["transaction_amount"] == 100
    assert first_exception.values["account_code"] == "4000"


def test_gl006_runs_without_helpful_fields(tmp_path: Path) -> None:
    """Only Entry User and Approval User should be required to execute."""

    _source_path, source = create_prepared_source(
        tmp_path,
        include_helpful_mapping=False,
    )

    result = SegregationOfDutiesProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.exception_count == 4
    assert result.metrics["journal_number_available"] is False
    assert result.metrics["account_code_available"] is False


def test_gl006_does_not_silently_exclude_system_accounts(tmp_path: Path) -> None:
    """Version 1.0 should disclose rather than invent system-account rules."""

    _source_path, source = create_prepared_source(tmp_path)

    result = SegregationOfDutiesProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert any(
        record.values["normalised_user"] == "system_batch" for record in result.exception_records
    )
    assert any("not automatically excluded" in limitation for limitation in result.limitations)


def test_gl006_honours_cooperative_cancellation(tmp_path: Path) -> None:
    """The procedure should stop promptly when cancellation is requested."""

    _source_path, source = create_prepared_source(tmp_path)

    token = ExecutionCancellationToken()
    token.cancel()

    with pytest.raises(AuditExecutionCancelledError):
        SegregationOfDutiesProcedure().run(
            context=create_context(source.dataset_id),
            source=source,
            cancellation_token=token,
        )


def test_gl006_runs_through_generic_test_engine(tmp_path: Path) -> None:
    """GL-006 should complete through the procedure-neutral Test Engine."""

    source_path, source = create_prepared_source(tmp_path)

    registry = ProcedureRegistry()
    registry.register(SegregationOfDutiesProcedure())

    outcome = EngineService(registry=registry).run(
        procedure_id="GL-006",
        source=source,
        source_path=source_path,
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.context.procedure_id == "GL006"
    assert outcome.result.exception_count == 4


def test_gl006_ranks_users_by_self_approval_concentration(tmp_path: Path) -> None:
    """Self-approval analysis should rank users and aggregate useful context."""

    _source_path, source = create_prepared_source(
        tmp_path,
        extra_rows=(
            (" alice ", "ALICE", "J008", 800, "4000", "Alice repeat"),
            ("Alice", "alice", "J009", 900, "4100", "Alice repeat"),
            ("Bob", "BOB", "J010", 1000, "5000", "Bob repeat"),
        ),
    )

    result = SegregationOfDutiesProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.exception_count == 7
    assert result.metrics["distinct_conflicting_users"] == 4
    assert result.metrics["highest_self_approval_count"] == 3
    assert result.metrics["top_user"] == "Alice"
    assert result.metrics["top_user_concentration_pct"] == pytest.approx((3 / 7) * 100.0)
    assert result.metrics["transaction_amount_available"] is True

    analysis = result.metrics["user_self_approval_analysis"]

    assert isinstance(analysis, tuple)
    assert tuple(row["normalised_user"] for row in analysis) == (
        "alice",
        "bob",
        "carol",
        "system_batch",
    )

    alice = analysis[0]

    assert alice["self_approvals"] == 3
    assert alice["affected_journals"] == 3
    assert alice["affected_accounts"] == 2
    assert alice["transaction_amount_total"] == 1800
    assert alice["transaction_amount_records"] == 3
