"""PAY001 deterministic membership, data quality, evidence, and integration tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.application_procedure_bootstrap import (
    create_application_procedure_registry,
)
from auditor_support_tool.core.audit_procedure_report_builder import AuditProcedureReportBuilder
from auditor_support_tool.core.data_profile_models import DetectedDataType
from auditor_support_tool.core.prepared_audit_dataset import PreparedAuditDataset
from auditor_support_tool.core.procedure_availability import ProcedureAvailabilityService
from auditor_support_tool.core.procedure_dataset_resolution import ProcedureDatasetSource
from auditor_support_tool.core.test_engine_models import TestEngineStatus as EngineStatus
from auditor_support_tool.core.test_engine_service import TestEngineService as EngineService
from auditor_support_tool.core.workbook_package import DatasetType
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.domains.financial_audit.payroll.procedure_bootstrap import (
    create_payroll_procedure_registry,
)
from auditor_support_tool.domains.financial_audit.payroll.procedure_catalogue import (
    PAY001_DEFINITION,
)
from auditor_support_tool.domains.financial_audit.payroll.procedures.payroll_gl_employee_validation import (  # noqa: E501
    PayrollGlEmployeeValidationProcedure,
)
from auditor_support_tool.presentation.result_presenter_registry import present_result

_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "regression"
    / "payroll_employee"
    / "payroll_staff_master_baseline.xlsx"
)

_HASH_PATH = _FIXTURE.parent / "baseline_sha256.txt"

_EXPECTED_EXCEPTION_ROWS_BY_EMPLOYEE = {
    "EMP-0057": [413, 764, 1031, 1313],
    "EMP-0102": [213],
    "EMP-0080": [188, 1130, 1259],
    "EMP-0109": [37, 293, 301, 927, 1087, 1101, 1421],
    "EMP-0117": [134, 287, 1104, 1306, 1588, 1789],
}

_GL_MAPPING = {
    "Transaction Date": "transaction_date",
    "Journal Number": "journal_number",
    "Account Code": "account_code",
    "Description": "transaction_description",
    "Debit Amount": "debit_amount",
    "Credit Amount": "credit_amount",
    "Net Amount": "transaction_amount",
    "Cost Centre": "cost_centre_code",
    "Employee Number": "employee_number",
}
_MASTER_MAPPING = {
    "Employee Number": "employee_id",
    "Employee Name": "employee_name",
    "Department": "department_code",
    "Employment Status": "employment_status",
}


def _map_dataset(dataset, mapping, dataset_type, dataset_id):
    dataset.confirmed_dataset_type = dataset_type
    dataset.dataset_id = dataset_id
    columns = {column.source_column: column for column in dataset.columns}
    field_mappings = {}
    for source_column, field_key in mapping.items():
        column = columns[source_column]
        column.confirmed_type = DetectedDataType.TEXT
        field_mappings[column.column_id] = field_key
    dataset.field_mappings = field_mappings
    return ProcedureDatasetSource.create(
        dataset_type=dataset_type,
        source=PreparedAuditDataset(dataset),
    )


def _sources(path):
    package = WorkbookPackageService().build_package(path)
    gl = package.get_dataset_by_worksheet("General_Ledger")
    master = package.get_dataset_by_worksheet("Staff_Master")
    assert gl is not None and master is not None
    return (
        _map_dataset(gl, _GL_MAPPING, DatasetType.GENERAL_LEDGER, "gl"),
        _map_dataset(master, _MASTER_MAPPING, DatasetType.EMPLOYEE_MASTER, "employees"),
    )


def _run(path, sources, parameters=None):
    return EngineService(registry=create_payroll_procedure_registry()).run(
        procedure_id="PAY001",
        source=sources[0].source,
        source_path=path,
        dataset_sources=sources,
        parameters=parameters,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
    )


def _synthetic_workbook(tmp_path, gl_rows, master_rows):
    workbook = Workbook()
    gl = workbook.active
    gl.title = "General_Ledger"
    gl.append(list(_GL_MAPPING))
    for index, (description, employee_number) in enumerate(gl_rows, start=1):
        gl.append(
            [
                "2026-01-01",
                f"J{index:03d}",
                "5000",
                description,
                "100",
                "0",
                "100",
                "CC1",
                employee_number,
            ]
        )
    master = workbook.create_sheet("Staff_Master")
    master.append(list(_MASTER_MAPPING))
    for employee_number, name, department, status in master_rows:
        master.append([employee_number, name, department, status])
    path = tmp_path / "pay001.xlsx"
    workbook.save(path)
    workbook.close()
    return path, _sources(path)


def test_pay001_registration_metadata_requirements_and_parameter():
    registry = create_application_procedure_registry()
    procedure = registry.require("PAY-001")
    assert isinstance(procedure, PayrollGlEmployeeValidationProcedure)
    assert procedure.definition is PAY001_DEFINITION
    assert PAY001_DEFINITION.category == "Payroll / Financial Audit"
    assert PAY001_DEFINITION.is_multi_dataset
    assert [
        (item.role, item.dataset_type, item.primary)
        for item in PAY001_DEFINITION.dataset_requirements
    ] == [
        ("general_ledger", DatasetType.GENERAL_LEDGER, True),
        ("employee_master", DatasetType.EMPLOYEE_MASTER, False),
    ]
    parameter = PAY001_DEFINITION.parameter_definitions[0]
    assert parameter.key == "payroll_descriptions"
    assert parameter.required is True
    assert parameter.default_value == (
        "Monthly salary allocation",
        "Payroll expense posting",
        "Overtime payroll posting",
    )
    assert "does not filter" in " ".join(PAY001_DEFINITION.limitations)
    assert "does not by itself establish" in PAY001_DEFINITION.result_meaning


def test_pay001_classification_identifier_safety_and_reconciliation(tmp_path):
    path, sources = _synthetic_workbook(
        tmp_path,
        gl_rows=[
            (" Monthly salary allocation ", " emp-1 "),
            ("PAYROLL EXPENSE POSTING", "EMP-2"),
            ("Overtime payroll posting", "EMP-3"),
            ("Monthly salary allocation", "EMP-4"),
            ("Monthly salary allocation", None),
            ("Monthly salary allocation", "DUP-1"),
            ("Monthly salary allocation", "NO-STATUS"),
            ("Monthly salary allocation", "001"),
            ("Monthly salary allocation", "EMP1"),
            ("Monthly salary allocation extra", "EMP-2"),
            ("Monthly salary", "EMP-2"),
        ],
        master_rows=[
            ("EMP-1", "Active Person", "Finance", "Active"),
            ("EMP-2", "Suspended Person", "Payroll", " Suspended "),
            ("EMP-3", "Terminated Person", "Operations", "Terminated"),
            ("DUP-1", "Duplicate One", "A", "Active"),
            (" dup-1 ", "Duplicate Two", "B", "Terminated"),
            ("NO-STATUS", "No Status", "C", None),
            ("1", "Numeric Looking", "D", "Active"),
            ("EMP-1-X", "Substring", "E", "Active"),
            (None, "Blank Identifier", "F", "Active"),
        ],
    )
    outcome = _run(path, sources)
    assert outcome.status == EngineStatus.COMPLETED, outcome.error_message
    result = outcome.result
    assert result is not None
    assert (result.population_count, result.records_evaluated_count) == (9, 6)
    assert (result.excluded_record_count, result.exception_count, result.non_exception_count) == (
        3,
        5,
        1,
    )
    assert result.exclusion_counts == {
        "blank_employee_number": 1,
        "ambiguous_employee_master_identifier": 1,
        "missing_employee_status": 1,
    }
    assert [record.reason_code for record in result.exception_records] == [
        "employee_not_active",
        "employee_not_active",
        "employee_not_found_in_master",
        "employee_not_found_in_master",
        "employee_not_found_in_master",
    ]
    assert [record.values["employee_number"] for record in result.exception_records] == [
        "EMP-2",
        "EMP-3",
        "EMP-4",
        "001",
        "EMP1",
    ]
    assert result.population_count == result.records_evaluated_count + result.excluded_record_count
    assert result.records_evaluated_count == result.exception_count + result.non_exception_count
    assert result.data_quality_observation_counts == {
        "blank_employee_number": 1,
        "ambiguous_employee_master_identifier": 1,
        "missing_employee_status": 1,
        "blank_employee_master_identifier": 1,
        "duplicate_employee_master_identifier": 1,
    }
    first = result.exception_records[0]
    assert first.source_row_number == 3
    assert first.source_record_id == "gl:row-3"
    assert first.values["employee_name"] == "Suspended Person"
    assert first.values["employment_status"] == " Suspended "
    assert first.values["department"] == "Payroll"
    assert result.metrics["total_gl_records_scanned"] == 11
    assert result.metrics["exception_current_status_distribution"] == {
        "Suspended": 1,
        "Terminated": 1,
    }


def test_pay001_parameter_override_changes_population_with_exact_matching(tmp_path):
    path, sources = _synthetic_workbook(
        tmp_path,
        gl_rows=[
            ("Custom payroll", "E1"),
            (" custom payroll ", "E1"),
            ("Custom payroll extra", "E1"),
            ("Monthly salary allocation", "E1"),
        ],
        master_rows=[("E1", "Employee", "Finance", "Active")],
    )
    result = _run(path, sources, {"payroll_descriptions": ["CUSTOM PAYROLL"]}).result
    assert result is not None
    assert (result.population_count, result.records_evaluated_count) == (2, 2)
    assert result.exception_count == 0
    assert result.context.parameters == {"payroll_descriptions": ["CUSTOM PAYROLL"]}


@pytest.mark.parametrize("missing", ["employee_master", "master_mapping", "gl_mapping"])
def test_pay001_generic_readiness_blocks_missing_inputs(tmp_path, missing):
    path, sources = _synthetic_workbook(
        tmp_path,
        gl_rows=[("Monthly salary allocation", "E1")],
        master_rows=[("E1", "Employee", "Finance", "Active")],
    )
    sources = list(sources)
    if missing == "employee_master":
        sources.pop()
    else:
        index = 1 if missing == "master_mapping" else 0
        dataset = sources[index].source.dataset
        dataset.field_mappings.clear()
        sources[index] = ProcedureDatasetSource.create(
            dataset_type=sources[index].dataset_type,
            source=PreparedAuditDataset(dataset),
        )
    available = ProcedureAvailabilityService().available_for_workspace(
        procedures=create_payroll_procedure_registry().procedures,
        active_source=sources[0],
        mapped_sources=sources,
    )
    assert not available
    outcome = _run(path, tuple(sources))
    assert outcome.status == EngineStatus.BLOCKED
    assert outcome.result is None


def test_pay001_regression_fixture_hash_is_frozen():
    """The PAY001 regression workbook must not change silently."""

    expected = _HASH_PATH.read_text(encoding="utf-8").strip()
    actual = hashlib.sha256(_FIXTURE.read_bytes()).hexdigest()

    assert actual == expected


def test_pay001_fixture_regression_membership_presentation_and_report():
    sources = _sources(_FIXTURE)
    result = _run(_FIXTURE, sources).result
    assert result is not None
    assert (
        result.metrics["total_gl_records_scanned"],
        result.population_count,
        result.records_evaluated_count,
        result.excluded_record_count,
        result.exception_count,
        result.non_exception_count,
    ) == (2000, 577, 467, 110, 21, 446)
    assert result.metrics["unmatched_employee_record_count"] == 0
    assert result.exclusion_counts == {"blank_employee_number": 110}
    actual_rows_by_employee: dict[str, list[int]] = {}
    for exception in result.exception_records:
        employee = str(exception.values["employee_number"])
        actual_rows_by_employee.setdefault(employee, []).append(exception.source_row_number)
        assert exception.source_record_id == f"gl:row-{exception.source_row_number}"
        assert exception.reason_code == "employee_not_active"
        assert exception.values["employment_status"] in {"Suspended", "Terminated"}

    assert actual_rows_by_employee == _EXPECTED_EXCEPTION_ROWS_BY_EMPLOYEE

    presentation = present_result(procedure_id="PAY001", result=result)
    assert len(presentation.table.rows) == 21
    assert any("data-quality" in text.lower() for text in presentation.observations)
    report = AuditProcedureReportBuilder().build(
        definition=PAY001_DEFINITION,
        result=result,
    )
    assert report.summary.population_count == 577
    assert report.summary.exception_count == 21
    assert len(report.exceptions) == 21
