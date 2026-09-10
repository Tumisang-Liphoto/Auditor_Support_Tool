"""Data Preparation page presentation regressions."""

import pytest
from PySide6.QtWidgets import QLabel

from auditor_support_tool.core.workbook_package import PreparationStatus
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.data_preparation_page import DataPreparationPage


@pytest.fixture
def page(qtbot):
    widget = DataPreparationPage(workspace_state=WorkspaceState())
    qtbot.addWidget(widget)
    widget.resize(1200, 900)
    widget.show()
    return widget


def test_preparation_uses_auditor_facing_actions(page):
    assert page._include_all_button.text() == "Select All"
    assert page._exclude_all_button.text() == "Clear Selection"
    assert page._reset_button.text() == "Reset Dataset"
    assert page._confirm_dataset_button.text() == "Confirm Dataset"
    assert page._continue_button.text() == "Continue to Field Mapping"


def test_dataset_section_exposes_progress(page):
    labels = [label.text() for label in page.findChildren(QLabel)]

    assert "Dataset" in labels
    assert "Preparation progress" in labels
    assert page._dataset_progress.text() == "0 of 0 datasets ready"


def test_preparation_table_uses_clear_type_wording(page):
    table = page._columns_table

    assert table.horizontalHeaderItem(1).text() == "Source Column"
    assert table.horizontalHeaderItem(2).text() == "Prepared Name"
    assert table.horizontalHeaderItem(3).text() == "Detected Type"
    assert table.horizontalHeaderItem(4).text() == "Use As"
    assert table.horizontalHeaderItem(6).text() == "Warning"


def test_changed_and_row_status_columns_are_hidden(page):
    table = page._columns_table

    assert table.isColumnHidden(5)
    assert table.isColumnHidden(7)
    assert not table.isColumnHidden(0)
    assert not table.isColumnHidden(1)
    assert not table.isColumnHidden(2)
    assert not table.isColumnHidden(3)
    assert not table.isColumnHidden(4)
    assert not table.isColumnHidden(6)


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (PreparationStatus.NOT_REVIEWED, "Needs confirmation"),
        (PreparationStatus.CONFIRMED, "Ready"),
        (PreparationStatus.CONFIRMED_WITH_WARNINGS, "Ready with warnings"),
        (PreparationStatus.REVIEW_REQUIRED, "Needs attention"),
        (PreparationStatus.EXCLUDED, "Excluded"),
    ),
)
def test_status_labels_are_action_oriented(status, expected):
    assert DataPreparationPage._status_label(status) == expected


@pytest.mark.parametrize(
    ("ready", "total", "expected"),
    (
        (0, 0, "0 of 0 datasets ready"),
        (0, 1, "0 of 1 dataset ready"),
        (1, 1, "1 of 1 dataset ready"),
        (1, 4, "1 of 4 datasets ready"),
        (4, 4, "4 of 4 datasets ready"),
    ),
)
def test_dataset_progress_text_uses_natural_pluralisation(ready, total, expected):
    assert DataPreparationPage._dataset_progress_text(ready, total) == expected


def test_not_reviewed_badge_is_not_presented_as_error():
    neutral_style = DataPreparationPage._status_badge_style(PreparationStatus.NOT_REVIEWED)
    attention_style = DataPreparationPage._status_badge_style(PreparationStatus.REVIEW_REQUIRED)

    assert neutral_style != attention_style
    assert "#6c757d" in neutral_style
    assert "#c62828" in attention_style


def test_default_guidance_is_actionable_when_dataset_is_available(page, monkeypatch):
    class Dataset:
        pass

    dataset = Dataset()

    monkeypatch.setattr(page, "_active_preparation_dataset", lambda: dataset)
    monkeypatch.setattr(page, "_refresh_dataset_selector", lambda: None)
    monkeypatch.setattr(page, "_refresh_dataset_status_list", lambda: None)
    monkeypatch.setattr(page, "_display_dataset", lambda _dataset: None)
    monkeypatch.setattr(page, "_populate_columns_table", lambda _dataset: None)
    monkeypatch.setattr(page, "_set_action_buttons_enabled", lambda _enabled: None)
    monkeypatch.setattr(page, "_update_confirm_button", lambda _dataset: None)
    monkeypatch.setattr(page, "_update_continue_button", lambda: None)

    page._preparation_status.setText("Select a confirmed dataset to begin.")
    page._refresh_page()

    assert (
        page._preparation_status.text()
        == "Review the dataset columns, then select Confirm Dataset."
    )
