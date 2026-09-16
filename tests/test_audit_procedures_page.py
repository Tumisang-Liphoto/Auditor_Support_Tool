"""Audit Procedures page presentation regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.procedure_execution_status_service import (
    ProcedureExecutionStatus,
)
from auditor_support_tool.core.workbook_package import DatasetType
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.audit_procedures_page import AuditProceduresPage
from auditor_support_tool.services.settings_service import SettingsService, UserProfile


class StubRegistry:
    """Minimal empty registry for page presentation tests."""

    procedures = ()

    def get(self, procedure_id: str):
        del procedure_id
        return None


@pytest.fixture
def page(qtbot):
    widget = AuditProceduresPage(
        workspace_state=WorkspaceState(),
        procedure_registry=StubRegistry(),
    )
    qtbot.addWidget(widget)
    widget.resize(1200, 900)
    widget.show()
    return widget


def test_empty_page_points_user_back_to_field_mapping(page):
    assert page._dataset_selector.isHidden()
    assert page._dataset_summary.text() == "No dataset is ready. Complete Field Mapping first."
    assert "Complete Field Mapping" in page._dataset_description.text()


def test_dataset_selector_is_hidden_when_only_one_dataset_exists(page):
    page._dataset_selector.clear()
    page._dataset_selector.addItem("General Ledger", "gl")
    page._update_dataset_selector_presentation()

    assert page._dataset_selector.isHidden()
    assert not page._dataset_selector.isEnabled()
    assert (
        page._dataset_description.text()
        == "Audit procedures will run against this analysis dataset. "
        "Supporting datasets are resolved automatically."
    )


def test_dataset_selector_is_shown_only_when_there_is_a_choice(page):
    page._dataset_selector.clear()
    page._dataset_selector.addItem("General Ledger", "gl")
    page._dataset_selector.addItem("Chart of Accounts", "coa")
    page._update_dataset_selector_presentation()

    assert not page._dataset_selector.isHidden()
    assert page._dataset_selector.isEnabled()
    assert "Choose the primary analysis dataset" in page._dataset_description.text()
    assert "Supporting datasets are resolved automatically" in page._dataset_description.text()


def test_reference_only_dataset_type_is_not_an_analysis_dataset(qtbot):
    gl011 = SimpleNamespace(
        definition=ProcedureDefinition.create(
            procedure_id="GL011",
            name="Unmapped Accounts",
            category="General Ledger",
            dataset_requirements=(
                ProcedureDatasetRequirement.create(
                    role="primary_data",
                    dataset_type=DatasetType.GENERAL_LEDGER,
                    required_fields=("account_code",),
                    primary=True,
                ),
                ProcedureDatasetRequirement.create(
                    role="reference_data",
                    dataset_type=DatasetType.CHART_OF_ACCOUNTS,
                    required_fields=("account_code",),
                ),
            ),
        )
    )
    registry = SimpleNamespace(
        procedures=(gl011,),
        get=lambda procedure_id: gl011 if procedure_id == "GL011" else None,
    )
    widget = AuditProceduresPage(
        workspace_state=WorkspaceState(),
        procedure_registry=registry,
    )
    qtbot.addWidget(widget)

    assert widget._supporting_only_dataset_types() == {DatasetType.CHART_OF_ACCOUNTS}


def test_dataset_type_used_as_primary_is_not_supporting_only(qtbot):
    mixed = SimpleNamespace(
        definition=ProcedureDefinition.create(
            procedure_id="PROC011",
            name="Mixed Dataset Example",
            category="Example",
            dataset_requirements=(
                ProcedureDatasetRequirement.create(
                    role="primary_data",
                    dataset_type=DatasetType.CHART_OF_ACCOUNTS,
                    required_fields=("account_code",),
                    primary=True,
                ),
                ProcedureDatasetRequirement.create(
                    role="reference_data",
                    dataset_type=DatasetType.GENERAL_LEDGER,
                    required_fields=("account_code",),
                ),
            ),
        )
    )
    registry = SimpleNamespace(
        procedures=(mixed,),
        get=lambda procedure_id: mixed if procedure_id == "PROC011" else None,
    )
    widget = AuditProceduresPage(
        workspace_state=WorkspaceState(),
        procedure_registry=registry,
    )
    qtbot.addWidget(widget)

    assert DatasetType.CHART_OF_ACCOUNTS not in widget._supporting_only_dataset_types()


def test_not_ready_procedure_card_disables_run_but_stays_visible(page):
    definition = ProcedureDefinition.create(
        procedure_id="GL011",
        name="Unmapped Accounts",
        category="General Ledger",
    )
    readiness = SimpleNamespace(
        can_run=False,
        dataset_readiness=(),
        missing_required_fields=("account_code",),
        mapped_required_fields=(),
        warnings=(),
    )

    row = page._build_procedure_row(
        definition,
        readiness,
        ProcedureExecutionStatus.NOT_RUN,
    )

    buttons = row.findChildren(type(page._back_button))
    run_button = next(button for button in buttons if button.text() == "Run")
    status_labels = row.findChildren(type(page._dataset_summary), "procedureExecutionStatus")

    assert not run_button.isEnabled()
    assert run_button.toolTip() == "Needs setup: Account Code"
    assert status_labels[0].text() == "Needs Setup"


@pytest.mark.parametrize(
    ("field_key", "expected"),
    (
        ("invoice_number", "Invoice Number"),
        ("transaction_date", "Transaction Date"),
        ("entry_user", "Entry User"),
        ("account_id", "Account ID"),
        ("general_ledger.account_code", "General Ledger: Account Code"),
        ("chart_of_accounts.account_code", "Chart Of Accounts: Account Code"),
    ),
)
def test_field_keys_are_presented_as_auditor_facing_labels(field_key, expected):
    assert AuditProceduresPage._friendly_field_name(field_key) == expected


def test_readiness_message_uses_friendly_required_field_names():
    readiness = SimpleNamespace(
        dataset_readiness=(),
        missing_required_fields=(),
        mapped_required_fields=("invoice_number", "transaction_date"),
        warnings=(),
    )

    assert (
        AuditProceduresPage._readiness_message(readiness)
        == "Required fields: Invoice Number ✓, Transaction Date ✓"
    )


def test_missing_fields_are_presented_as_setup_work():
    readiness = SimpleNamespace(
        dataset_readiness=(),
        missing_required_fields=("invoice_number",),
        mapped_required_fields=(),
        warnings=(),
    )

    assert AuditProceduresPage._readiness_message(readiness) == "Needs setup: Invoice Number"


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (ProcedureExecutionStatus.NOT_RUN, "Ready to Run"),
        (ProcedureExecutionStatus.COMPLETED, "✓ Completed"),
        (ProcedureExecutionStatus.NEEDS_RERUN, "↻ Needs Re-run"),
    ),
)
def test_execution_status_uses_actionable_wording(status, expected):
    assert AuditProceduresPage._execution_status_text(status) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (ProcedureExecutionStatus.NOT_RUN, "Run"),
        (ProcedureExecutionStatus.COMPLETED, "Run Again"),
        (ProcedureExecutionStatus.NEEDS_RERUN, "Re-run"),
    ),
)
def test_run_button_wording_is_compact(status, expected):
    assert AuditProceduresPage._run_button_text(status) == expected


def test_methodology_summary_shows_objective_and_isa_basis() -> None:
    definition = ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        audit_objective="Identify weekend-dated transactions for auditor evaluation.",
        isa_references=("ISA 240, paragraph 33(a)", "ISA 240, A42-A45"),
        isa_basis_type="ISA-supported methodology",
        audit_rationale="Journal-entry testing provides the audit context.",
        result_meaning="A configured weekend date was identified.",
        limitations=("Weekend activity may be legitimate.",),
    )

    summary = AuditProceduresPage._methodology_summary(definition)

    assert "Objective: Identify weekend-dated transactions" in summary
    assert "ISA 240, paragraph 33(a)" in summary
    assert "ISA 240, A42-A45" in summary
    assert "ISA-supported methodology" in summary


def test_methodology_summary_is_empty_for_legacy_definition() -> None:
    definition = ProcedureDefinition.create(
        procedure_id="PROC001",
        name="Legacy Procedure",
        category="Example",
    )

    assert AuditProceduresPage._methodology_summary(definition) == ""


def test_execution_identity_comes_from_current_user_profile(qtbot, tmp_path) -> None:
    """A procedure run should snapshot the existing local User Profile fields."""

    settings = SettingsService(tmp_path / "settings.ini")
    settings.save_user_profile(
        UserProfile(
            preferred_name="Example",
            full_name="Example Auditor",
            job_title="Senior Auditor",
            organization="Example Audit Office",
            directorate="Financial Audit",
        )
    )
    widget = AuditProceduresPage(
        workspace_state=WorkspaceState(),
        procedure_registry=StubRegistry(),
        settings_service=settings,
    )
    qtbot.addWidget(widget)

    executor = widget._execution_user_identity()

    assert executor.full_name == "Example Auditor"
    assert executor.job_title == "Senior Auditor"
    assert executor.directorate == "Financial Audit"
    assert executor.organization == "Example Audit Office"
