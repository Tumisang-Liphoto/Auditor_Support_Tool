"""End-to-end regression checks for the frozen General Ledger baseline."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
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

_FIXTURE_DIRECTORY = Path(__file__).resolve().parent / "fixtures" / "regression" / "general_ledger"
_MAPPING_PATH = _FIXTURE_DIRECTORY / "mapping_manifest.json"
_EXPECTED_PATH = _FIXTURE_DIRECTORY / "expected_results.json"
_HASH_PATH = _FIXTURE_DIRECTORY / "baseline_sha256.txt"

_DECIMAL_METRICS = {
    "saturday_debit_total",
    "saturday_credit_total",
    "sunday_debit_total",
    "sunday_credit_total",
    "weekend_debit_total",
    "weekend_credit_total",
}


def _load_json(path: Path) -> dict[str, object]:
    """Load one regression manifest."""

    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline() -> tuple[
    Path,
    PreparedAuditDataset,
    dict[str, object],
]:
    """Build the mapped prepared dataset from the frozen regression workbook."""

    mapping_manifest = _load_json(_MAPPING_PATH)
    expected_manifest = _load_json(_EXPECTED_PATH)

    workbook_path = _FIXTURE_DIRECTORY / str(expected_manifest["workbook_file"])

    package = WorkbookPackageService().build_package(workbook_path)
    dataset = package.get_dataset_by_worksheet(str(mapping_manifest["dataset_sheet"]))

    assert dataset is not None

    columns_by_name = {column.source_column: column for column in dataset.columns}

    field_mappings: dict[str, str] = {}

    for mapping in mapping_manifest["field_mappings"]:
        source_column = str(mapping["source_column"])
        standard_field = str(mapping["standard_field"])
        confirmed_type = str(mapping["confirmed_type"])

        column = columns_by_name[source_column]
        column.confirmed_type = getattr(
            DetectedDataType,
            confirmed_type,
        )
        field_mappings[column.column_id] = standard_field

    dataset.field_mappings = field_mappings

    return (
        workbook_path,
        PreparedAuditDataset(dataset),
        expected_manifest,
    )


def _run_baseline_procedure(
    *,
    procedure_id: str,
    workbook_path: Path,
    source: PreparedAuditDataset,
    manifest: dict[str, object],
):
    """Run one baseline procedure through the real generic Test Engine."""

    audit_period = manifest["audit_period"]
    parameters = manifest["procedure_parameters"][procedure_id]

    outcome = EngineService(registry=create_general_ledger_procedure_registry()).run(
        procedure_id=procedure_id,
        source=source,
        source_path=workbook_path,
        audit_period_start=str(audit_period["start"]),
        audit_period_end=str(audit_period["end"]),
        parameters=parameters,
    )

    assert outcome.status == EngineStatus.COMPLETED
    assert outcome.error_message == ""
    assert outcome.result is not None

    _assert_source_visibility(outcome.result, source)
    return outcome.result


def _assert_common_result(
    *,
    result,
    expected: dict[str, object],
    manifest: dict[str, object],
) -> None:
    """Assert common counts and reproducibility fields."""

    assert result.population_count == expected["population_count"]
    assert result.records_evaluated_count == expected["records_evaluated_count"]
    assert result.exception_count == expected["exception_count"]
    assert result.exclusion_counts == expected["exclusion_counts"]

    assert result.context.audit_period_start == manifest["audit_period"]["start"]
    assert result.context.audit_period_end == manifest["audit_period"]["end"]

    expected_rows = expected["exception_source_rows"]
    actual_rows = [record.source_row_number for record in result.exception_records]

    assert actual_rows == expected_rows


def _assert_metric_subset(
    *,
    actual: dict[str, object],
    expected: dict[str, object],
) -> None:
    """Compare the stable metrics recorded in the regression manifest."""

    for key, expected_value in expected.items():
        assert key in actual

        actual_value = actual[key]

        if key in _DECIMAL_METRICS:
            assert Decimal(str(actual_value)) == Decimal(str(expected_value))
            continue

        if isinstance(expected_value, float):
            assert float(actual_value) == pytest.approx(expected_value)
            continue

        assert actual_value == expected_value


def test_general_ledger_regression_fixture_integrity(
    baseline: tuple[
        Path,
        PreparedAuditDataset,
        dict[str, object],
    ],
) -> None:
    """The frozen workbook must not change without an explicit baseline update."""

    workbook_path, source, manifest = baseline

    actual_hash = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
    hash_file_value = _HASH_PATH.read_text(encoding="utf-8").split()[0]

    assert actual_hash == manifest["workbook_sha256"]
    assert actual_hash == hash_file_value
    assert source.record_count == manifest["record_count"]


def test_gl001_regression_baseline(
    baseline: tuple[
        Path,
        PreparedAuditDataset,
        dict[str, object],
    ],
) -> None:
    """GL-001 must retain its known-good duplicate-invoice result."""

    workbook_path, source, manifest = baseline
    expected = manifest["expected"]["GL001"]

    result = _run_baseline_procedure(
        procedure_id="GL001",
        workbook_path=workbook_path,
        source=source,
        manifest=manifest,
    )

    _assert_common_result(
        result=result,
        expected=expected,
        manifest=manifest,
    )
    _assert_metric_subset(
        actual=result.metrics,
        expected=expected["metrics"],
    )

    grouped_records: dict[str, list] = defaultdict(list)

    for record in result.exception_records:
        grouped_records[str(record.values["normalised_invoice_number"])].append(record)

    actual_groups = []

    for normalised_invoice, records in grouped_records.items():
        actual_groups.append(
            {
                "normalised_invoice_number": normalised_invoice,
                "source_rows": [record.source_row_number for record in records],
                "vendor_codes": sorted({str(record.values["vendor_code"]) for record in records}),
            }
        )

    actual_groups.sort(key=lambda group: group["source_rows"][0])

    assert actual_groups == expected["duplicate_groups"]


def test_gl003_regression_baseline(
    baseline: tuple[
        Path,
        PreparedAuditDataset,
        dict[str, object],
    ],
) -> None:
    """GL-003 must retain its known-good weekend result."""

    workbook_path, source, manifest = baseline
    expected = manifest["expected"]["GL003"]

    result = _run_baseline_procedure(
        procedure_id="GL003",
        workbook_path=workbook_path,
        source=source,
        manifest=manifest,
    )

    _assert_common_result(
        result=result,
        expected=expected,
        manifest=manifest,
    )
    _assert_metric_subset(
        actual=result.metrics,
        expected=expected["metrics"],
    )


def test_gl006_regression_baseline(
    baseline: tuple[
        Path,
        PreparedAuditDataset,
        dict[str, object],
    ],
) -> None:
    """GL-006 must retain its known-good self-approval result."""

    workbook_path, source, manifest = baseline
    expected = manifest["expected"]["GL006"]

    result = _run_baseline_procedure(
        procedure_id="GL006",
        workbook_path=workbook_path,
        source=source,
        manifest=manifest,
    )

    _assert_common_result(
        result=result,
        expected=expected,
        manifest=manifest,
    )
    _assert_metric_subset(
        actual=result.metrics,
        expected=expected["metrics"],
    )

    actual_analysis = result.metrics["user_self_approval_analysis"]
    expected_analysis = expected["user_self_approval_analysis"]

    assert len(actual_analysis) == len(expected_analysis)

    for actual_row, expected_row in zip(
        actual_analysis,
        expected_analysis,
        strict=True,
    ):
        assert actual_row["user"] == expected_row["user"]
        assert actual_row["normalised_user"] == expected_row["normalised_user"]
        assert actual_row["self_approvals"] == expected_row["self_approvals"]
        assert float(actual_row["exception_share_pct"]) == pytest.approx(
            expected_row["exception_share_pct"]
        )
        assert actual_row["affected_journals"] == expected_row["affected_journals"]
        assert actual_row["affected_accounts"] == expected_row["affected_accounts"]
        assert Decimal(str(actual_row["transaction_amount_total"])) == Decimal(
            str(expected_row["transaction_amount_total"])
        )
        assert (
            actual_row["transaction_amount_records"] == expected_row["transaction_amount_records"]
        )


def test_gl011_regression_baseline(qtbot, tmp_path):
    """Frozen GL rows 1956-1958 use 9999, absent from the existing 29-account COA."""
    from auditor_support_tool.core.procedure_dataset_resolution import ProcedureDatasetSource
    from auditor_support_tool.core.workbook_package import DatasetType

    mapping = _load_json(_MAPPING_PATH)
    manifest = _load_json(_EXPECTED_PATH)
    path = _FIXTURE_DIRECTORY / manifest["workbook_file"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["workbook_sha256"]
    package = WorkbookPackageService().build_package(path)
    descriptors = []
    for item in mapping["gl011_dataset_mappings"]:
        dataset = package.get_dataset_by_worksheet(item["dataset_sheet"])
        dataset_type = getattr(DatasetType, item["dataset_type"])
        dataset.confirmed_dataset_type = dataset_type
        column = next(c for c in dataset.columns if c.source_column == item["source_column"])
        column.confirmed_type = getattr(DetectedDataType, item["confirmed_type"])
        dataset.field_mappings = {column.column_id: item["standard_field"]}
        descriptors.append(
            ProcedureDatasetSource.create(
                dataset_type=dataset_type,
                source=PreparedAuditDataset(dataset),
            )
        )
    outcome = EngineService(registry=create_general_ledger_procedure_registry()).run(
        procedure_id="GL011",
        source=descriptors[0].source,
        source_path=path,
        dataset_sources=descriptors,
        audit_period_start=manifest["audit_period"]["start"],
        audit_period_end=manifest["audit_period"]["end"],
        parameters=manifest["procedure_parameters"]["GL011"],
    )
    assert outcome.status == EngineStatus.COMPLETED
    result = outcome.result
    expected = manifest["expected"]["GL011"]
    _assert_common_result(result=result, expected=expected, manifest=manifest)
    _assert_metric_subset(actual=result.metrics, expected=expected["metrics"])
    assert [str(e.values["account_code"]) for e in result.exception_records] == expected[
        "exception_account_codes"
    ]
    assert result.exception_rate == pytest.approx(0.15)
    assert result.context.mapping_fingerprint != descriptors[0].source.mapping_fingerprint
    _assert_source_visibility(result, descriptors[0].source)
    _assert_report_exports(result, descriptors[0].source, tmp_path)

    from auditor_support_tool.core.workspace_state import WorkspaceState
    from auditor_support_tool.gui.pages.results_page import ResultsPage

    state = WorkspaceState()
    state.set_workbook_package(package)
    # Resolution follows execution identity, even when another sheet is active.
    state.set_active_dataset(descriptors[1].source.dataset_id)
    page = ResultsPage(
        workspace_state=state, procedure_registry=create_general_ledger_procedure_registry()
    )
    qtbot.addWidget(page)
    page.set_outcome(outcome)
    assert page._exceptions_table.rowCount() == 3
    assert [page._exceptions_table.item(i, 0).text() for i in range(3)] == ["1956", "1957", "1958"]
    assert page._source_records.headers == descriptors[0].source.dataset.loaded_table.headers
    assert all(
        page._source_records.records[(e.source_record_id, e.source_row_number)]
        for e in result.exception_records
    )


def _assert_source_visibility(result, source):
    """Every baseline exception displays its own raw cells through generic enrichment."""
    from copy import deepcopy

    from auditor_support_tool.presentation.exception_source_records import (
        add_source_columns,
        resolve_exception_sources,
    )
    from auditor_support_tool.presentation.result_presenter_registry import present_result

    before = deepcopy(result)
    sources = resolve_exception_sources(result, (source.dataset,))
    table = add_source_columns(
        present_result(procedure_id=result.context.procedure_id, result=result).table, sources
    )
    expected = {record.source_record_id: record for record in source.iter_records()}
    assert len(table.rows) == result.exception_count
    for row in table.rows:
        record = expected[row.values["record_id"]]
        assert row.values["source_row"] == str(record.source_row_number)
        for index, header in enumerate(source.dataset.loaded_table.headers):
            value = record.raw_row[header]
            assert row.values[f"source:{index}"] == ("" if value is None else str(value))
            assert table.columns[index + 1].label == header
    assert result == before


def _assert_report_exports(result, source, tmp_path):
    from openpyxl import load_workbook

    from auditor_support_tool.presentation.exception_source_records import resolve_exception_sources
    from auditor_support_tool.presentation.report_export_document import ReportExportRequest
    from auditor_support_tool.services.audit_export_service import AuditExportService
    from tests.test_auditor_report_export import docx_text, pdf_text

    definition = (
        create_general_ledger_procedure_registry().require(result.context.procedure_id).definition
    )
    request = ReportExportRequest(
        definition, result, resolve_exception_sources(result, (source.dataset,))
    )
    for format in ("pdf", "docx", "xlsx"):
        path = tmp_path / (result.context.procedure_id + "." + format)
        AuditExportService().export_report(request, path, format)
        if format == "pdf":
            text = pdf_text(path)
        elif format == "docx":
            text = docx_text(path)
        else:
            book = load_workbook(path)
            rows = list(book["Exceptions"].values)
            assert len(rows) == result.exception_count + 1
            assert [row[0] for row in rows[1:]] == [
                str(e.source_row_number) for e in result.exception_records
            ]
            text = "\n".join(str(value) for row in rows for value in row)
            book.close()
        assert all(e.source_record_id in text for e in result.exception_records)


@pytest.mark.parametrize("procedure_id", ("GL001", "GL003", "GL006"))
def test_baseline_auditor_report_formats(baseline, procedure_id, tmp_path, qapp):
    path, source, manifest = baseline
    result = _run_baseline_procedure(
        procedure_id=procedure_id, workbook_path=path, source=source, manifest=manifest
    )
    _assert_report_exports(result, source, tmp_path)
