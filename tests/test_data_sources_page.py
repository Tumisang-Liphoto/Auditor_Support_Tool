"""Data Sources page UX and presentation regressions."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QLabel

from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.data_sources_page import DataSourcesPage


@pytest.fixture
def page(qtbot):
    widget = DataSourcesPage(workspace_state=WorkspaceState())
    qtbot.addWidget(widget)
    widget.resize(1200, 850)
    widget.show()
    return widget


def test_data_sources_presents_simple_audit_workflow(page):
    visible_labels = {label.text() for label in page.findChildren(QLabel)}

    assert "Select File" in visible_labels
    assert "Select Data to Include" in visible_labels
    assert page._browse_button.text() == "Select File"
    assert page._load_package_button.text() == "Load Data"
    assert page._confirm_button.text() == "Continue to Data Profile"
    assert page._select_all_button.text() == "Select All"
    assert page._exclude_all_button.text() == "Clear Selection"
    assert page._path_field.placeholderText() == "No file selected"

    # Clearing the entire audit is deliberately not offered from Data Sources.
    assert page._clear_button.isHidden()


def test_navigator_hides_internal_confidence_and_status_columns(page):
    table = page._navigator_table

    assert table.horizontalHeaderItem(1).text() == "Source"
    assert table.horizontalHeaderItem(2).text() == "Dataset Name"
    assert table.horizontalHeaderItem(3).text() == "Dataset Type"
    assert table.isColumnHidden(6)
    assert table.isColumnHidden(7)


def test_selected_file_shows_filename_and_preserves_full_path_as_tooltip(page):
    path = Path("audit-data") / "general_ledger.xlsx"
    source_info = SimpleNamespace(
        path=path,
        file_type="xlsx",
        file_size_bytes=2048,
        worksheets=(object(), object()),
    )

    page._display_source_metadata(source_info)

    assert page._path_field.text() == "general_ledger.xlsx"
    assert page._path_field.toolTip() == str(path)
    assert page._file_type_value.text() == "XLSX"
    assert page._file_size_value.text() == "2.00 KB"
    assert page._worksheet_count_value.text() == "2"
    assert page._loaded_dataset_count_value.text() == "0"


def test_reset_restores_stage_two_labels(page):
    page._load_package_button.setText("Reload Data")
    page._path_field.setText("general_ledger.xlsx")
    page._path_field.setToolTip("audit-data/general_ledger.xlsx")

    page._reset_page()

    assert page._load_package_button.text() == "Load Data"
    assert page._path_field.text() == ""
    assert page._path_field.toolTip() == ""
    assert page._source_status.text() == "Select a source file to begin."


def test_reload_data_is_presented_as_secondary_action(page):
    page._set_load_button_mode(reload=True)

    assert page._load_package_button.text() == "Reload Data"
    assert page._load_package_button.objectName() == "secondaryActionButton"

    page._set_load_button_mode(reload=False)

    assert page._load_package_button.text() == "Load Data"
    assert page._load_package_button.objectName() == "primaryActionButton"


@pytest.mark.parametrize(
    ("count", "expected"),
    (
        (1, "1 dataset"),
        (4, "4 datasets"),
        (1200, "1,200 datasets"),
    ),
)
def test_dataset_count_text_uses_natural_pluralisation(page, count, expected):
    assert page._dataset_count_text(count) == expected


def test_empty_source_status_is_hidden(page):
    page._set_source_status("", "neutral")

    assert page._source_status.text() == ""
    assert page._source_status.isHidden()


def test_clear_handler_requests_transition_without_clearing_state(page, qtbot):
    from auditor_support_tool.core.workspace_models import WorkspaceIdentity

    state = page._workspace_state
    identity = WorkspaceIdentity.create(name="Unsaved audit")
    state.start_workspace(identity)
    with qtbot.waitSignal(page.clear_requested):
        page._clear_workspace()
    assert state.workspace_identity is identity
    assert state.is_dirty
    assert page._clear_button.isHidden()
