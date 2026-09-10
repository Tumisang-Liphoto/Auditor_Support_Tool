"""Audit Procedures page presentation regressions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from auditor_support_tool.core.procedure_execution_status_service import (
    ProcedureExecutionStatus,
)
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.audit_procedures_page import AuditProceduresPage


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
        page._dataset_description.text() == "Audit procedures will run against this mapped dataset."
    )


def test_dataset_selector_is_shown_only_when_there_is_a_choice(page):
    page._dataset_selector.clear()
    page._dataset_selector.addItem("General Ledger", "gl")
    page._dataset_selector.addItem("Chart of Accounts", "coa")
    page._update_dataset_selector_presentation()

    assert not page._dataset_selector.isHidden()
    assert page._dataset_selector.isEnabled()
    assert "Choose the mapped dataset" in page._dataset_description.text()


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
