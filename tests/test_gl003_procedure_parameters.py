"""Tests for configurable GL-003 Weekend Transactions parameters."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from auditor_support_tool.core.data_profile_models import DetectedDataType
from auditor_support_tool.core.prepared_audit_dataset import PreparedAuditDataset
from auditor_support_tool.core.procedure_parameter_models import ProcedureParameterType
from auditor_support_tool.core.procedure_registry import ProcedureRegistry
from auditor_support_tool.core.test_engine_models import (
    TestEngineStatus as EngineStatus,
)
from auditor_support_tool.core.test_engine_service import (
    TestEngineService as EngineService,
)
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    weekend_transactions,
)

WeekendTransactionsProcedure = weekend_transactions.WeekendTransactionsProcedure


def _source(tmp_path: Path) -> tuple[Path, PreparedAuditDataset]:
    """Create a small mapped population containing Friday, Saturday and Sunday."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"
    worksheet.append(
        [
            "Transaction Date",
            "Journal Number",
            "Journal Type",
            "Journal Source",
        ]
    )
    worksheet.append(["2026-01-02", "J001", "Automated", "AP"])
    worksheet.append(["2026-01-03", "J002", "Manual", "GL"])
    worksheet.append(["2026-01-04", "J003", "Automated", "Manual"])

    source_path = tmp_path / "gl003-parameters.xlsx"
    workbook.save(source_path)

    package = WorkbookPackageService().build_package(source_path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    date_column = next(
        column for column in dataset.columns if column.source_column == "Transaction Date"
    )
    journal_column = next(
        column for column in dataset.columns if column.source_column == "Journal Number"
    )
    journal_type_column = next(
        column for column in dataset.columns if column.source_column == "Journal Type"
    )
    journal_source_column = next(
        column for column in dataset.columns if column.source_column == "Journal Source"
    )

    date_column.confirmed_type = DetectedDataType.DATE
    journal_column.confirmed_type = DetectedDataType.TEXT
    journal_type_column.confirmed_type = DetectedDataType.TEXT
    journal_source_column.confirmed_type = DetectedDataType.TEXT

    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
        journal_column.column_id: "journal_number",
        journal_type_column.column_id: "journal_type",
        journal_source_column.column_id: "journal_source",
    }

    return source_path, PreparedAuditDataset(dataset)


def _engine() -> EngineService:
    """Return a Test Engine with the real GL-003 implementation registered."""

    registry = ProcedureRegistry()
    registry.register(WeekendTransactionsProcedure())
    return EngineService(registry=registry)


def test_gl003_catalogue_defines_supported_configuration() -> None:
    """GL-003 should expose its configurable settings through the catalogue."""

    entry = require_general_ledger_procedure("GL003")
    definitions = {parameter.key: parameter for parameter in entry.parameter_definitions}

    assert tuple(definitions) == (
        "weekend_days",
        "high_value_threshold",
        "manual_journal_values",
    )
    assert definitions["weekend_days"].value_type == (ProcedureParameterType.MULTI_CHOICE)
    assert definitions["weekend_days"].default_value == (
        "Saturday",
        "Sunday",
    )


def test_engine_records_default_weekend_days_in_run_context(tmp_path: Path) -> None:
    """Running without configuration should record the Saturday/Sunday default."""

    source_path, source = _source(tmp_path)

    outcome = _engine().run(
        procedure_id="GL003",
        source=source,
        source_path=source_path,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.context.parameters == {
        "weekend_days": [
            "Saturday",
            "Sunday",
        ]
    }
    assert outcome.result.exception_count == 2
    assert outcome.result.metrics["saturday_transactions"] == 1
    assert outcome.result.metrics["sunday_transactions"] == 1


def test_gl003_respects_independently_selected_weekend_days(tmp_path: Path) -> None:
    """Deselected Sunday should not be reported as a weekend exception."""

    source_path, source = _source(tmp_path)

    outcome = _engine().run(
        procedure_id="GL003",
        source=source,
        source_path=source_path,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
        parameters={"weekend_days": ["Saturday"]},
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.context.parameters["weekend_days"] == ["Saturday"]
    assert outcome.result.exception_count == 1
    assert outcome.result.metrics["saturday_transactions"] == 1
    assert outcome.result.metrics["sunday_transactions"] == 0
    assert outcome.result.exception_records[0].values["day_of_week"] == "Saturday"


def test_manual_indicator_matches_journal_type_or_source(tmp_path: Path) -> None:
    """Configured manual values should match either mapped classification field."""

    source_path, source = _source(tmp_path)

    outcome = _engine().run(
        procedure_id="GL003",
        source=source,
        source_path=source_path,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
        parameters={
            "weekend_days": ["Sunday"],
            "manual_journal_values": ["Manual"],
        },
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.result is not None
    assert outcome.result.exception_count == 1
    assert outcome.result.metrics["manual_journal_available"] is True
    assert outcome.result.metrics["manual_journal_weekend_count"] == 1
    assert outcome.result.exception_records[0].values["risk_indicators"] == ("manual_journal",)
