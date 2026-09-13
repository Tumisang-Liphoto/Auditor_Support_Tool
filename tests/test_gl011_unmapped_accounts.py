"""GL011 transaction-level membership, evidence and generic integration."""

from dataclasses import replace
from hashlib import sha256

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.audit_execution_models import ExecutionCancellationToken
from auditor_support_tool.core.audit_procedure_report_builder import AuditProcedureReportBuilder
from auditor_support_tool.core.data_profile_models import DetectedDataType
from auditor_support_tool.core.prepared_audit_dataset import PreparedAuditDataset
from auditor_support_tool.core.procedure_availability import ProcedureAvailabilityService
from auditor_support_tool.core.procedure_dataset_resolution import ProcedureDatasetSource
from auditor_support_tool.core.test_description_catalogue import (
    get_test_description_definition,
    has_test_description_document,
)
from auditor_support_tool.core.test_engine_models import TestEngineStatus as EngineStatus
from auditor_support_tool.core.test_engine_service import TestEngineService as EngineService
from auditor_support_tool.core.workbook_package import DatasetType
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_bootstrap import (
    create_general_ledger_procedure_registry,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedures import (
    unmapped_accounts,
)
from auditor_support_tool.presentation.result_presenter_registry import present_result
from auditor_support_tool.services.audit_export_service import AuditExportService


def make_sources(tmp_path, gl=None, coa=None, account_type=DetectedDataType.TEXT):
    """A small synthetic workbook; labels retain blank-account rows during import."""
    if gl is None:
        gl = ["120", " ab-C ", "9999", " 9999 ", "00120", "AB", "closed1", None, " ", " MiSs-2 "]
    if coa is None:
        coa = ["120", "AB-c", "A.B", "closed1", " ab-C ", None, " "]
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, values in (("Ledger", gl), ("Accounts", coa)):
        sheet = workbook.create_sheet(name)
        sheet.append(["Account", "Status"])
        for value in values:
            sheet.append([value, "closed"])
    path = tmp_path / "gl011.xlsx"
    workbook.save(path)
    workbook.close()
    package = WorkbookPackageService().build_package(path)
    descriptors = []
    for sheet, dataset_type, identity in (
        ("Ledger", DatasetType.GENERAL_LEDGER, "gl"),
        ("Accounts", DatasetType.CHART_OF_ACCOUNTS, "coa"),
    ):
        dataset = package.get_dataset_by_worksheet(sheet)
        dataset.dataset_id = identity
        dataset.confirmed_dataset_type = dataset_type
        column = next(c for c in dataset.columns if c.source_column == "Account")
        column.column_id = identity + "-account"
        column.confirmed_type = account_type
        dataset.field_mappings = {column.column_id: "account_code"}
        descriptors.append(
            ProcedureDatasetSource.create(
                dataset_type=dataset_type,
                source=PreparedAuditDataset(dataset),
            )
        )
    return path, tuple(descriptors)


def run_gl011(path, descriptors, **kwargs):
    return EngineService(registry=create_general_ledger_procedure_registry()).run(
        procedure_id="GL011",
        source=descriptors[0].source,
        source_path=path,
        dataset_sources=descriptors,
        **kwargs,
    )


def test_gl011_registration_definition_and_bundled_description():
    registry = create_general_ledger_procedure_registry()
    procedure = registry.require("GL-011")
    assert isinstance(procedure, unmapped_accounts.UnmappedAccountsProcedure)
    assert procedure.definition is require_general_ledger_procedure("GL011").definition
    assert [
        (r.role, r.dataset_type, r.required_fields, r.primary)
        for r in procedure.definition.dataset_requirements
    ] == [
        ("general_ledger", DatasetType.GENERAL_LEDGER, ("account_code",), True),
        ("chart_of_accounts", DatasetType.CHART_OF_ACCOUNTS, ("account_code",), False),
    ]
    assert procedure.definition.parameter_definitions == ()
    assert procedure.definition.procedure_version == "1.0"
    assert get_test_description_definition("GL011").title == "Unmapped Accounts"
    assert has_test_description_document("GL-011")


def test_gl011_membership_counts_traceability_and_full_population(tmp_path):
    path, descriptors = make_sources(tmp_path)
    available = ProcedureAvailabilityService().available_for_workspace(
        procedures=create_general_ledger_procedure_registry().procedures,
        active_source=descriptors[0],
        mapped_sources=descriptors,
    )
    assert "GL011" in {item.procedure.definition.procedure_id for item in available}
    # No date mapping is required; recording a period does not restrict this population.
    outcome = run_gl011(
        path, descriptors, audit_period_start="2026-01-01", audit_period_end="2026-01-31"
    )
    assert outcome.status == EngineStatus.COMPLETED
    result = outcome.result
    assert (
        result.population_count,
        result.records_evaluated_count,
        result.excluded_record_count,
    ) == (10, 8, 2)
    assert result.exclusion_counts == {"blank_account_code": 2}
    assert result.exception_count == 5
    assert result.exception_rate == 62.5
    assert result.metrics == {
        "unique_unmapped_account_count": 4,
        "unique_reference_account_count": 4,
        "reference_record_count": 7,
        "blank_reference_account_count": 2,
        "duplicate_reference_account_count": 1,
        "reference_dataset_id": "coa",
    }
    assert [e.source_row_number for e in result.exception_records] == [4, 5, 6, 7, 11]
    assert [e.source_record_id for e in result.exception_records] == [
        "gl:row-4",
        "gl:row-5",
        "gl:row-6",
        "gl:row-7",
        "gl:row-11",
    ]
    assert [e.values for e in result.exception_records] == [
        {"account_code": "9999", "normalised_account_code": "9999"},
        {"account_code": " 9999 ", "normalised_account_code": "9999"},
        {"account_code": "00120", "normalised_account_code": "00120"},
        {"account_code": "AB", "normalised_account_code": "ab"},
        {"account_code": " MiSs-2 ", "normalised_account_code": "miss-2"},
    ]
    assert result.context.dataset_id == "gl"
    assert result.context.source_sha256 == sha256(path.read_bytes()).hexdigest()
    assert result.context.audit_period_start == "2026-01-01"
    assert result.context.audit_period_end == "2026-01-31"
    assert result.context.parameters == {}
    assert any("does not filter" in text for text in result.limitations)
    assert any("status" in text for text in result.limitations)


def test_gl011_preserves_text_identity_despite_numeric_preparation(tmp_path):
    path, descriptors = make_sources(
        tmp_path,
        gl=["00120", "120", "AB-C", "A.B"],
        coa=["120", "ab-c", "AB"],
        account_type=DetectedDataType.INTEGER,
    )
    result = run_gl011(path, descriptors).result
    assert [e.values["account_code"] for e in result.exception_records] == ["00120", "A.B"]
    assert result.records_evaluated_count == 4


@pytest.mark.parametrize(
    ("gl", "coa", "evaluated", "exceptions"),
    [
        (["120"], ["120"], 1, 0),
        ([None, " "], ["120"], 0, 0),
        (["120"], ["120", None, " "], 1, 0),
        (["120"], [None, " "], None, None),
    ],
)
def test_gl011_zero_exceptions_and_empty_membership(tmp_path, gl, coa, evaluated, exceptions):
    path, descriptors = make_sources(tmp_path, gl=gl, coa=coa)
    outcome = run_gl011(path, descriptors)
    if evaluated is None:
        assert outcome.status == EngineStatus.FAILED
        assert outcome.result is None
        assert "contains no nonblank account identifiers" in outcome.error_message
        return
    assert outcome.status == EngineStatus.COMPLETED
    result = outcome.result
    assert result.records_evaluated_count == evaluated
    assert result.exception_count == exceptions
    assert result.exception_rate == (100.0 if exceptions else 0.0)
    assert result.population_count == evaluated + result.excluded_record_count
    if None in coa:
        assert result.metrics["blank_reference_account_count"] == 2
        assert any("2 blank account record(s)" in text for text in result.limitations)


@pytest.mark.parametrize("missing", ["gl_mapping", "coa_dataset", "coa_mapping", "ambiguous_coa"])
def test_gl011_generic_readiness_blocks_incomplete_or_ambiguous_sources(tmp_path, missing):
    path, descriptors = make_sources(tmp_path)
    descriptors = list(descriptors)
    if missing in {"gl_mapping", "coa_mapping"}:
        index = 0 if missing == "gl_mapping" else 1
        dataset = descriptors[index].source.dataset
        dataset.field_mappings.clear()
        descriptors[index] = replace(descriptors[index], source=PreparedAuditDataset(dataset))
    elif missing == "coa_dataset":
        descriptors.pop()
    else:
        duplicate = replace(descriptors[1].source.dataset, dataset_id="another-coa")
        descriptors.append(replace(descriptors[1], source=PreparedAuditDataset(duplicate)))
    registry = create_general_ledger_procedure_registry()
    available = ProcedureAvailabilityService().available_for_workspace(
        procedures=registry.procedures,
        active_source=descriptors[0],
        mapped_sources=descriptors,
    )
    assert all(item.procedure.definition.procedure_id != "GL011" for item in available)
    outcome = run_gl011(path, descriptors)
    assert outcome.status == EngineStatus.BLOCKED
    assert outcome.result is None
    assert not outcome.was_executed


@pytest.mark.parametrize("role_index", [0, 1])
def test_gl011_honours_cancellation_in_both_populations(tmp_path, role_index, monkeypatch):
    path, descriptors = make_sources(tmp_path)
    token = ExecutionCancellationToken()
    source = descriptors[role_index].source
    original = source.iter_records

    def cancel_during_iteration():
        for record in original():
            token.cancel()
            yield record

    monkeypatch.setattr(source, "iter_records", cancel_during_iteration)
    outcome = run_gl011(path, descriptors, cancellation_token=token)
    assert outcome.status == EngineStatus.CANCELLED
    assert outcome.result is None


def test_gl011_combined_mapping_fingerprint_changes_with_reference_mapping(tmp_path):
    path, descriptors = make_sources(tmp_path)
    first = run_gl011(path, descriptors).result
    repeat = run_gl011(path, descriptors).result
    assert first.context.mapping_fingerprint == repeat.context.mapping_fingerprint
    assert first.exception_records == repeat.exception_records
    assert first.context.execution_id != repeat.context.execution_id
    assert first.context.mapping_fingerprint != descriptors[0].source.mapping_fingerprint
    reference = descriptors[1].source.dataset
    reference.columns[0].confirmed_type = DetectedDataType.INTEGER
    changed = (descriptors[0], replace(descriptors[1], source=PreparedAuditDataset(reference)))
    later = run_gl011(path, changed).result
    assert first.context.mapping_fingerprint != later.context.mapping_fingerprint
    assert first.exception_records == later.exception_records


def test_gl011_generic_presentation_report_and_export_keep_all_exceptions(tmp_path):
    path, descriptors = make_sources(tmp_path)
    result = run_gl011(path, descriptors).result
    presentation = present_result(procedure_id="GL011", result=result)
    assert len(presentation.table.rows) == 5
    assert [row.values["record_id"] for row in presentation.table.rows] == [
        e.source_record_id for e in result.exception_records
    ]
    report = AuditProcedureReportBuilder().build(
        definition=unmapped_accounts.UnmappedAccountsProcedure().definition,
        result=result,
    )
    assert report.summary.exception_count == 5
    assert report.metrics["unique_unmapped_account_count"] == 4
    assert [e.source_row_number for e in report.exceptions] == [4, 5, 6, 7, 11]
    assert report.mapping_fingerprint == result.context.mapping_fingerprint
    target = tmp_path / "gl011-report.json"
    AuditExportService().export_report_json(report, target)
    assert '"00120"' in target.read_text(encoding="utf-8")
    assert report.report_fingerprint in target.read_text(encoding="utf-8")


@pytest.mark.parametrize("role_index", [0, 1])
def test_gl011_rejects_unsupported_account_values_without_false_results(tmp_path, role_index):
    path, descriptors = make_sources(
        tmp_path,
        gl=[True] if role_index == 0 else ["120"],
        coa=[True] if role_index == 1 else ["120"],
    )
    outcome = run_gl011(path, descriptors)
    assert outcome.status == EngineStatus.FAILED
    assert outcome.result is None
    assert "text or finite numbers" in outcome.error_message
