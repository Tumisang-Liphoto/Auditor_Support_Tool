"""Tests for GL-001 Duplicate Invoice Detection."""

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
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_bootstrap import (
    create_general_ledger_procedure_registry,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    duplicate_invoice_detection,
)

DuplicateInvoiceDetectionProcedure = duplicate_invoice_detection.DuplicateInvoiceDetectionProcedure


def create_prepared_source(
    tmp_path: Path,
    *,
    include_vendor_mapping: bool = True,
) -> tuple[Path, PreparedAuditDataset]:
    """Create a representative mapped population for GL-001."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Audit_Data"

    worksheet.append(
        [
            "Invoice Number",
            "Vendor Code",
            "Vendor Name",
            "Posting Date",
            "Journal Reference",
            "Amount",
            "Narrative",
        ]
    )
    worksheet.append(
        [
            "INV-1001",
            "V001",
            "Alpha Supplies",
            "2026-01-02",
            "J001",
            100,
            "First Alpha posting",
        ]
    )
    worksheet.append(
        [
            "inv-1001",
            "V001",
            "Alpha Supplies",
            "2026-01-03",
            "J002",
            100,
            "Second Alpha posting",
        ]
    )
    worksheet.append(
        [
            "  INV-1001  ",
            "V001",
            "Alpha Supplies",
            "2026-01-04",
            "J003",
            100,
            "Third Alpha posting",
        ]
    )
    worksheet.append(
        [
            "INV-2002",
            "V002",
            "Beta Traders",
            "2026-01-05",
            "J004",
            200,
            "Beta posting",
        ]
    )
    worksheet.append(
        [
            "INV-2002",
            "V003",
            "Gamma Traders",
            "2026-01-06",
            "J005",
            200,
            "Gamma posting",
        ]
    )
    worksheet.append(
        [
            "INV-3003",
            "V004",
            "Delta Traders",
            "2026-01-07",
            "J006",
            300,
            "Unique invoice",
        ]
    )
    worksheet.append(
        [
            None,
            "V005",
            "Blank Invoice Vendor",
            "2026-01-08",
            "J007",
            400,
            "Blank invoice",
        ]
    )
    worksheet.append(
        [
            "   ",
            "V006",
            "Whitespace Invoice Vendor",
            "2026-01-09",
            "J008",
            500,
            "Whitespace invoice",
        ]
    )

    source_path = tmp_path / "gl001.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("Audit_Data")

    assert dataset is not None

    columns = {column.source_column: column for column in dataset.columns}

    columns["Invoice Number"].confirmed_type = DetectedDataType.TEXT
    columns["Vendor Code"].confirmed_type = DetectedDataType.TEXT
    columns["Vendor Name"].confirmed_type = DetectedDataType.TEXT
    columns["Posting Date"].confirmed_type = DetectedDataType.DATE
    columns["Journal Reference"].confirmed_type = DetectedDataType.TEXT
    columns["Amount"].confirmed_type = DetectedDataType.DECIMAL
    columns["Narrative"].confirmed_type = DetectedDataType.TEXT

    field_mappings = {
        columns["Invoice Number"].column_id: "invoice_number",
        columns["Posting Date"].column_id: "transaction_date",
        columns["Journal Reference"].column_id: "journal_number",
        columns["Amount"].column_id: "transaction_amount",
        columns["Narrative"].column_id: "transaction_description",
    }

    if include_vendor_mapping:
        field_mappings.update(
            {
                columns["Vendor Code"].column_id: "vendor_code",
                columns["Vendor Name"].column_id: "vendor_name",
            }
        )

    dataset.field_mappings = field_mappings

    return (
        source_path,
        PreparedAuditDataset(dataset),
    )


def create_context(
    dataset_id: str,
) -> ProcedureRunContext:
    """Create a valid GL-001 run context."""

    request = AuditExecutionRequest.create(
        procedure_id="GL001",
        dataset_id=dataset_id,
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )


def test_gl001_uses_authoritative_catalogue_definition() -> None:
    """The real procedure should use the existing catalogue definition."""

    procedure = DuplicateInvoiceDetectionProcedure()

    assert procedure.definition.procedure_id == "GL001"
    assert procedure.definition.display_id == "GL-001"
    assert procedure.definition.required_fields == ("invoice_number",)
    assert procedure.definition.parameter_definitions == ()


def test_gl001_flags_all_records_in_repeated_invoice_groups(
    tmp_path: Path,
) -> None:
    """Trimmed case-insensitive repeats should return every group record."""

    _source_path, source = create_prepared_source(tmp_path)

    result = DuplicateInvoiceDetectionProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.population_count == 8
    assert result.records_evaluated_count == 6
    assert result.excluded_record_count == 2

    assert result.exception_count == 5
    assert result.metrics["duplicate_groups"] == 2
    assert result.metrics["additional_duplicate_records"] == 3

    assert result.exclusion_counts == {
        "blank_invoice_number": 2,
    }

    first_group = result.exception_records[:3]

    assert {record.values["normalised_invoice_number"] for record in first_group} == {"inv-1001"}

    assert {record.values["duplicate_group_size"] for record in first_group} == {3}


def test_gl001_vendor_relationship_is_supporting_context(
    tmp_path: Path,
) -> None:
    """Vendor analysis should classify groups without changing exceptions."""

    _source_path, source = create_prepared_source(tmp_path)

    result = DuplicateInvoiceDetectionProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.metrics["vendor_analysis_available"] is True
    assert result.metrics["same_vendor_groups"] == 1
    assert result.metrics["multiple_vendor_groups"] == 1
    assert result.metrics["vendor_not_assessable_groups"] == 0

    relationships = {
        record.values["normalised_invoice_number"]: record.values["vendor_relationship"]
        for record in result.exception_records
    }

    assert relationships["inv-1001"] == "Same vendor"
    assert relationships["inv-2002"] == "Multiple vendors"


def test_gl001_retains_source_traceability_and_helpful_fields(
    tmp_path: Path,
) -> None:
    """Flagged rows should retain source identity and mapped context."""

    _source_path, source = create_prepared_source(tmp_path)

    result = DuplicateInvoiceDetectionProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    first_exception = result.exception_records[0]

    assert first_exception.source_row_number == 2
    assert first_exception.source_record_id.endswith(":row-2")
    assert first_exception.reason_code == "DUPLICATE_INVOICE_NUMBER"

    assert first_exception.values["invoice_number"] == "INV-1001"
    assert first_exception.values["vendor_code"] == "V001"
    assert first_exception.values["vendor_name"] == "Alpha Supplies"
    assert first_exception.values["journal_number"] == "J001"
    assert first_exception.values["transaction_amount"] == 100


def test_gl001_runs_without_vendor_fields_and_discloses_limitation(
    tmp_path: Path,
) -> None:
    """Vendor context should remain optional and never block GL-001."""

    _source_path, source = create_prepared_source(
        tmp_path,
        include_vendor_mapping=False,
    )

    result = DuplicateInvoiceDetectionProcedure().run(
        context=create_context(source.dataset_id),
        source=source,
        cancellation_token=ExecutionCancellationToken(),
    )

    assert result.exception_count == 5
    assert result.metrics["vendor_analysis_available"] is False
    assert result.metrics["vendor_not_assessable_groups"] == 2
    assert result.limitations == (
        "Vendor Code and Vendor Name are not mapped; vendor relationship analysis is unavailable.",
    )


def test_gl001_honours_cooperative_cancellation(
    tmp_path: Path,
) -> None:
    """The procedure should stop promptly when cancellation is requested."""

    _source_path, source = create_prepared_source(tmp_path)

    token = ExecutionCancellationToken()
    token.cancel()

    with pytest.raises(AuditExecutionCancelledError):
        DuplicateInvoiceDetectionProcedure().run(
            context=create_context(source.dataset_id),
            source=source,
            cancellation_token=token,
        )


def test_gl001_runs_through_generic_test_engine(
    tmp_path: Path,
) -> None:
    """GL-001 should complete through the procedure-neutral engine."""

    source_path, source = create_prepared_source(tmp_path)

    registry = ProcedureRegistry()
    registry.register(DuplicateInvoiceDetectionProcedure())

    outcome = EngineService(registry=registry).run(
        procedure_id="GL-001",
        source=source,
        source_path=source_path,
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.context.procedure_id == "GL001"
    assert outcome.result.exception_count == 5


def test_gl001_and_gl003_are_registered_as_executable_procedures() -> None:
    """The GL bootstrap should expose both implemented procedures."""

    registry = create_general_ledger_procedure_registry()

    assert tuple(procedure.definition.procedure_id for procedure in registry.procedures) == (
        "GL001",
        "GL003",
        "GL006",
    )
