"""Tests for creating and editing audit details."""

from PySide6.QtCore import QDate

from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.gui.dialogs.new_workspace_dialog import NewWorkspaceDialog


def test_edit_dialog_prepopulates_and_preserves_audit_identity(qtbot) -> None:
    """Editing should retain stable audit identifiers while changing details."""

    identity = WorkspaceIdentity.create(
        name="General Ledger Audit",
        auditee_name="Example Ministry",
        audit_year="2026",
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
        audit_domain="Financial Audit",
        audit_area="General Ledger",
        lead_auditor="Auditor One",
        description="Initial scope",
    )
    dialog = NewWorkspaceDialog(existing_identity=identity)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Edit Audit Details"
    assert dialog._workspace_name_input.text() == "General Ledger Audit"
    assert dialog._auditee_name_input.text() == "Example Ministry"
    assert dialog._audit_year_input.currentText() == "2026"
    assert dialog._audit_period_start_input.date() == QDate(2026, 4, 1)
    assert dialog._audit_period_end_input.date() == QDate(2027, 3, 31)
    assert dialog._audit_domain_combo.currentData() == "Financial Audit"
    assert dialog._audit_area_input.text() == "General Ledger"
    assert dialog._lead_auditor_input.text() == "Auditor One"
    assert dialog._description_input.toPlainText() == "Initial scope"

    dialog._workspace_name_input.setText("Updated GL Audit")
    dialog._audit_period_end_input.setDate(QDate(2027, 6, 30))
    dialog._accept_workspace()

    updated = dialog.workspace_identity

    assert updated is not None
    assert updated.workspace_id == identity.workspace_id
    assert updated.created_at == identity.created_at
    assert updated.modified_at == identity.modified_at
    assert updated.name == "Updated GL Audit"
    assert updated.audit_period_start == "2026-04-01"
    assert updated.audit_period_end == "2027-06-30"


def test_edit_dialog_locks_audit_domain_after_data_load(qtbot) -> None:
    """The dialog should make a locked audit domain visibly non-editable."""

    identity = WorkspaceIdentity.create(
        name="General Ledger Audit",
        audit_domain="Financial Audit",
    )
    dialog = NewWorkspaceDialog(
        existing_identity=identity,
        lock_audit_domain=True,
    )
    qtbot.addWidget(dialog)

    assert dialog._audit_domain_combo.isEnabled() is False
    assert "cannot be changed" in dialog._audit_domain_combo.toolTip()


def test_edit_dialog_preserves_legacy_blank_period_and_year(qtbot) -> None:
    """Editing an older audit should not silently invent a year or period."""

    identity = WorkspaceIdentity.create(name="Legacy Audit")
    dialog = NewWorkspaceDialog(existing_identity=identity)
    qtbot.addWidget(dialog)

    assert dialog._audit_year_input.currentData() == ""
    assert dialog._audit_period_start_input.specialValueText() == "Not specified"
    assert dialog._audit_period_end_input.specialValueText() == "Not specified"

    dialog._accept_workspace()

    updated = dialog.workspace_identity

    assert updated is not None
    assert updated.audit_year == ""
    assert updated.audit_period_start == ""
    assert updated.audit_period_end == ""


def test_new_audit_dialog_still_defaults_to_current_year_and_dates(qtbot) -> None:
    """The edit capability must not regress the normal New Audit workflow."""

    dialog = NewWorkspaceDialog()
    qtbot.addWidget(dialog)

    today = QDate.currentDate()

    assert dialog.windowTitle() == "New Audit"
    assert dialog._audit_year_input.currentData() == today.year()
    assert dialog._audit_period_start_input.date() == today
    assert dialog._audit_period_end_input.date() == today
