"""Results explorer behaviour and batched column-sizing regressions."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QLabel, QStyledItemDelegate

from auditor_support_tool.core.audit_execution_models import AuditExecutionRequest
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineOutcome as EngineOutcome,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineStatus as EngineStatus,
)
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_bootstrap import (
    create_general_ledger_procedure_registry,
)
from auditor_support_tool.gui.pages import results_page
from auditor_support_tool.presentation.result_dashboard_models import DashboardIndicator


@pytest.fixture
def page(qtbot):
    """Show 120 source-linked exceptions, spanning three pages and two groups."""
    registry = create_general_ledger_procedure_registry()
    context = ProcedureRunContext.create(
        request=AuditExecutionRequest.create(procedure_id="GL001", dataset_id="dataset-1"),
        procedure_version=registry.require("GL001").definition.procedure_version,
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )
    records = tuple(
        ProcedureExceptionRecord.create(
            source_record_id=f"dataset-1:row-{i + 2}",
            source_row_number=i + 2,
            reason_code="DUPLICATE_INVOICE_NUMBER",
            reason="Repeated invoice number.",
            values={
                "invoice_number": f"INV-{i // 2:03}",
                "duplicate_group_id": f"group-{i // 2}",
                "duplicate_group_size": 2,
                "vendor_relationship": "Same vendor" if i < 60 else "Multiple vendors",
                "transaction_amount": Decimal("1234.50"),
                "transaction_description": f"Review transaction {i:03}",
            },
        )
        for i in range(120)
    )
    result = ProcedureResult.create(
        context=context,
        population_count=120,
        records_evaluated_count=120,
        exception_records=records,
        metrics={
            "duplicate_groups": 60,
            "flagged_records": 120,
            "additional_duplicate_records": 60,
            "vendor_analysis_available": True,
            "same_vendor_groups": 30,
            "multiple_vendor_groups": 30,
            "same_vendor_records": 60,
            "multiple_vendor_records": 60,
        },
    )
    widget = results_page.ResultsPage(workspace_state=WorkspaceState(), procedure_registry=registry)
    qtbot.addWidget(widget)
    widget.resize(1200, 900)
    widget.show()
    widget.set_outcome(EngineOutcome("GL001", "dataset-1", EngineStatus.COMPLETED, result=result))
    qtbot.waitExposed(widget)
    return widget


def assert_visible_rows(page, expected):
    table = page._exceptions_table
    columns = page._presentation.table.columns
    assert table.rowCount() == len(expected)
    for row_index, row in enumerate(expected):
        for column_index, column in enumerate(columns):
            item = table.item(row_index, column_index)
            assert item.text() == row.values.get(column.key, "—")
            assert item.toolTip() == f"Source record: {row.values['record_id']}"


def test_rows_and_pagination(page):
    rows = page._presentation.table.rows
    assert_visible_rows(page, rows[:50])
    assert page._exceptions_table.item(0, 0).text() == "2"
    assert page._exceptions_table.item(0, 4).text() == "1,234.50"
    assert page._exceptions_table.item(0, 0).textAlignment() & Qt.AlignmentFlag.AlignRight
    assert page._page_label.text() == "Page 1 of 3"
    assert not page._previous_page_button.isEnabled()
    page._next_page_button.click()
    assert_visible_rows(page, rows[50:100])
    page._next_page_button.click()
    assert_visible_rows(page, rows[100:])
    assert page._page_label.text() == "Page 3 of 3"
    assert not page._next_page_button.isEnabled()
    page._previous_page_button.click()
    assert_visible_rows(page, rows[50:100])


def test_search_and_filter_intersection_and_empty_state(page):
    rows = page._presentation.table.rows
    page._next_page_button.click()
    action = next(a for a in page._filters_button.menu().actions() if a.data() == "same_vendor")
    action.trigger()
    assert page._page_label.text() == "Page 1 of 2"
    assert_visible_rows(page, rows[:50])
    page._search_input.setText("  inv-029  ")
    assert_visible_rows(page, rows[58:60])
    assert page._table_count_label.text() == "2 of 120 exceptions"
    page._search_input.setText("no matching transaction")
    assert_visible_rows(page, ())
    assert page._page_label.text() == "Page 1 of 1"
    assert not page._next_page_button.isEnabled()
    page._search_input.clear()
    button = next(
        b
        for b in page._filter_button_group.buttons()
        if b.property("filter_key") == "multiple_vendors"
    )
    button.click()
    assert_visible_rows(page, rows[60:110])


def test_column_visibility_and_sizing_survive_page_changes(page):
    table = page._exceptions_table
    header = table.horizontalHeader()
    assert header.sectionResizeMode(5) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Interactive
    assert table.columnWidth(1) >= table.sizeHintForColumn(1)
    action = page._columns_button.menu().actions()[1]
    action.setChecked(False)
    page._next_page_button.click()
    assert table.isColumnHidden(1)
    action.setChecked(True)
    assert not table.isColumnHidden(1)
    assert table.item(0, 1).text() == "INV-025"


def test_cell_insertion_does_not_remeasure_columns(page, monkeypatch, qapp):
    table = page._exceptions_table

    class MeasuringDelegate(QStyledItemDelegate):
        inserting = False
        measurements_during_insertion = 0

        def sizeHint(self, option, index):
            if self.inserting:
                self.measurements_during_insertion += 1
            return super().sizeHint(option, index)

    delegate = MeasuringDelegate(table)
    table.setItemDelegate(delegate)
    qapp.processEvents()
    original = table.setItem

    def insert(*args):
        delegate.inserting = True
        try:
            original(*args)
        finally:
            delegate.inserting = False

    monkeypatch.setattr(table, "setItem", insert)
    page._next_page_button.click()
    qapp.processEvents()
    assert delegate.measurements_during_insertion == 0
    assert_visible_rows(page, page._presentation.table.rows[50:100])


def test_exploration_preserves_result_and_full_report(page, monkeypatch):
    result = page.outcome.result
    snapshot = deepcopy(result)
    definition = page._procedure_registry.require("GL001").definition
    before = page._report_builder.build(definition=definition, result=result).to_json()
    captured = []

    class ReportDialog:
        def __init__(self, *, report, parent):
            captured.append(report.to_json())

        def exec(self):
            return 0

    monkeypatch.setattr(results_page, "AuditProcedureReportDialog", ReportDialog)
    page._next_page_button.click()
    page._set_filter("same_vendor")
    page._search_input.setText("INV-029")
    page._columns_button.menu().actions()[1].setChecked(False)
    page._view_report_button.click()
    assert page.outcome.result is result
    assert result == snapshot
    assert captured == [before]


def test_placeholder_result_actions_are_hidden(page):
    """Unavailable actions should not occupy the normal auditor workflow."""

    assert not hasattr(page, "_export_button")
    assert page._export_exceptions_button.isEnabled()


def test_empty_filters_are_not_shown(page):
    """A filter should only be offered when it can select at least one exception."""

    filter_keys = {button.property("filter_key") for button in page._filter_button_group.buttons()}

    assert "same_vendor" in filter_keys
    assert "multiple_vendors" in filter_keys
    assert "not_assessable" not in filter_keys


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("12", True),
        ("0", True),
        ("N/A", False),
        ("n/a", False),
        ("Not available", False),
        ("—", False),
        ("", False),
    ),
)
def test_display_availability_hides_only_unavailable_values(value, expected):
    assert results_page.ResultsPage._display_value_is_available(value) is expected


@pytest.mark.parametrize("include_available", (True, False))
def test_unavailable_analysis_preserves_titles_and_reasons(page, qapp, include_available):
    """Mixed and wholly unavailable analysis retain compact presenter explanations."""

    available = page._presentation.risk_indicators[0]
    unavailable = (
        DashboardIndicator("Amount analysis", "N/A", "Threshold not configured", available=False),
        DashboardIndicator(
            "User analysis", "N/A", "Required user fields unavailable", available=False
        ),
    )
    presentation = replace(
        page._presentation,
        risk_indicators=((available,) if include_available else ()) + unavailable,
    )
    page._populate_risk_panel(presentation)
    qapp.processEvents()

    assert page._risk_panel.isVisible()
    assert page._risk_heading.isVisible()
    assert page._risk_heading.text() == presentation.risk_title
    assert page._risk_description.isVisible()
    assert page._risk_description.text() == presentation.risk_description
    layout = page._risk_items_layout
    assert layout.count() == (2 if include_available else 1)
    if include_available:
        card = layout.itemAt(0).widget()
        assert card.isVisible()
        assert card.objectName() == "card"
        texts = [label.text() for label in card.findChildren(QLabel)]
        assert available.title in texts
        assert available.detail in texts
        assert available.value in texts

    disclosure = layout.itemAt(layout.count() - 1).widget()
    assert isinstance(disclosure, QLabel)
    assert disclosure.isVisible()
    for indicator in unavailable:
        assert f"{indicator.title} — {indicator.detail}" in disclosure.text()
    assert "N/A" not in disclosure.text()


@pytest.mark.parametrize("status", (EngineStatus.BLOCKED, EngineStatus.FAILED))
@pytest.mark.parametrize("hidden_metric", ("missing", "unavailable"))
def test_no_result_restores_fallback_metric_visibility(page, monkeypatch, status, hidden_metric):
    """Fallback cards must not inherit hidden state from a completed presentation."""

    metrics = page._presentation.metrics
    presentation = replace(
        page._presentation,
        metrics=(
            metrics[:-1]
            if hidden_metric == "missing"
            else metrics[:-1] + (replace(metrics[-1], value="N/A"),)
        ),
    )
    monkeypatch.setattr(results_page, "present_result", lambda **kwargs: presentation)
    page.set_outcome(page.outcome)
    assert page._metric_cards[-1].isHidden()

    page.set_outcome(EngineOutcome("GL001", "dataset-1", status))

    assert len(page._metric_cards) == 4
    for card, title in zip(
        page._metric_cards, ("Population", "Evaluated", "Exceptions", "Exception %"), strict=True
    ):
        assert card.isVisible()
        texts = [label.text() for label in card.findChildren(QLabel)]
        assert title in texts
        assert "—" in texts


@pytest.mark.parametrize("status", (EngineStatus.BLOCKED, EngineStatus.FAILED))
def test_no_result_resets_exception_explorer_state(page, status):
    """Failed or blocked outcomes must not retain prior exception navigation state."""

    completed_outcome = page.outcome
    page._next_page_button.click()
    assert page._page_label.text() == "Page 2 of 3"
    assert page._table_count_label.text() == "120 of 120 exceptions"
    assert page._previous_page_button.isEnabled()

    page.set_outcome(EngineOutcome("GL001", "dataset-1", status))

    assert page._filtered_rows == ()
    assert page._active_filter == "all"
    assert page._current_page == 1
    assert page._search_input.text() == ""
    assert not page._search_input.isEnabled()
    assert page._filter_buttons_layout.count() == 0
    assert page._filters_button.isHidden()
    assert not page._filters_button.isEnabled()
    assert not page._columns_button.isEnabled()
    assert page._exceptions_table.rowCount() == 0
    assert page._exceptions_table.columnCount() == 0
    assert page._table_count_label.text() == "0 of 0 exceptions"
    assert page._page_label.text() == "Page 1 of 1"
    assert not page._previous_page_button.isEnabled()
    assert not page._next_page_button.isEnabled()

    page.set_outcome(completed_outcome)

    assert page._search_input.isEnabled()
    assert page._columns_button.isEnabled()
    assert page._table_count_label.text() == "120 of 120 exceptions"
    assert page._page_label.text() == "Page 1 of 3"
    assert not page._previous_page_button.isEnabled()
    assert page._next_page_button.isEnabled()


@pytest.mark.parametrize(
    "signal_name",
    (
        "source_changed",
        "workbook_package_changed",
        "active_dataset_changed",
        "workspace_cleared",
    ),
)
def test_execution_input_changes_clear_displayed_result(page, signal_name):
    """Execution-relevant workspace changes must not leave a completed result displayed."""

    assert page.outcome is not None

    signal = getattr(page._workspace_state, signal_name)
    signal.emit()

    assert page.outcome is None
    assert page._presentation is None
    assert page._empty_state.isVisible()
    assert not page._result_content.isVisible()


def test_displayed_procedure_parameter_change_clears_result(page):
    """Changing parameters for the displayed procedure invalidates its visible result."""

    assert page.outcome is not None

    page._workspace_state.procedure_parameters_changed.emit("gl001")

    assert page.outcome is None
    assert page._presentation is None


def test_other_procedure_parameter_change_preserves_result(page):
    """Unrelated procedure settings must not clear the currently displayed result."""

    outcome = page.outcome

    page._workspace_state.procedure_parameters_changed.emit("GL003")

    assert page.outcome is outcome
    assert page._presentation is not None


def test_export_cancel_preserves_exploration(page, monkeypatch):
    page._set_filter("same_vendor")
    page._search_input.setText("INV-029")
    snapshot = deepcopy(page.outcome.result)
    monkeypatch.setattr(results_page.QFileDialog, "getSaveFileName", lambda *args: ("", ""))
    page._export_exceptions()
    assert page._export_worker is None
    assert page.outcome.result == snapshot
    assert page._search_input.text() == "INV-029"
    assert page._active_filter == "same_vendor"


def test_export_uses_complete_result_and_feedback(page, monkeypatch, tmp_path, qtbot):
    page._next_page_button.click()
    page._set_filter("same_vendor")
    page._search_input.setText("INV-029")
    original = deepcopy(page.outcome.result)
    dirty_before = page._workspace_state.is_dirty
    target = tmp_path / "all.csv"
    monkeypatch.setattr(
        results_page.QFileDialog, "getSaveFileName", lambda *args: (str(target), "CSV (*.csv)")
    )
    messages = []
    monkeypatch.setattr(
        results_page.QMessageBox, "information", lambda *args: messages.append(args[2])
    )
    page._export_exceptions()
    qtbot.waitUntil(lambda: page._export_worker is None)
    import csv

    with target.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == original.exception_count == 120
    assert [row["source_record_id"] for row in rows] == [
        r.source_record_id for r in original.exception_records
    ]
    assert page.outcome.result == original
    assert page._workspace_state.is_dirty == dirty_before
    assert page._search_input.text() == "INV-029"
    assert page._active_filter == "same_vendor"
    assert messages


def test_export_error_and_invalidated_state(page, monkeypatch, qtbot, tmp_path):
    target = tmp_path / "missing" / "all.xlsx"
    monkeypatch.setattr(
        results_page.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(target), "Excel Workbook (*.xlsx)"),
    )
    errors = []
    monkeypatch.setattr(results_page.QMessageBox, "warning", lambda *args: errors.append(args[2]))
    original = page.outcome
    page._export_exceptions()
    qtbot.waitUntil(lambda: page._export_worker is None)
    assert errors
    assert page.outcome is original
    assert page._export_exceptions_button.isEnabled()
    page.clear_result()
    assert not page._export_exceptions_button.isEnabled()


def test_zero_exception_export_enabled(page):
    outcome = replace(
        page.outcome,
        result=replace(
            page.outcome.result, exception_records=(), exception_count=0, exception_rate=0
        ),
    )
    page.set_outcome(outcome)
    assert page._export_exceptions_button.isEnabled()
    assert "all 0 exceptions" in page._export_exceptions_button.toolTip()


def test_csv_selection_changes_default_suffix_without_unapproved_overwrite(
    page, monkeypatch, tmp_path
):
    existing = tmp_path / "all.csv"
    existing.write_bytes(b"existing")
    monkeypatch.setattr(
        results_page.QFileDialog,
        "getSaveFileName",
        lambda *args: (str(tmp_path / "all.xlsx"), "CSV (*.csv)"),
    )
    questions = []

    def decline(*args):
        questions.append(args)
        return results_page.QMessageBox.StandardButton.No

    monkeypatch.setattr(results_page.QMessageBox, "question", decline)
    page._export_exceptions()
    assert questions
    assert page._export_worker is None
    assert existing.read_bytes() == b"existing"
