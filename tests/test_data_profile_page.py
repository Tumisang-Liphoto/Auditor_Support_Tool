"""Data Profile page presentation regressions."""

import pytest
from PySide6.QtWidgets import QHeaderView

from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.data_profile_page import DataProfilePage


@pytest.fixture
def page(qtbot):
    widget = DataProfilePage(workspace_state=WorkspaceState())
    qtbot.addWidget(widget)
    widget.resize(1200, 900)
    widget.show()
    return widget


def test_profile_uses_auditor_facing_labels(page):
    assert page._continue_button.text() == "Continue to Data Preparation"

    summary_card = page._dataset_selector.parentWidget()
    visible_text = " ".join(
        label.text() for label in summary_card.findChildren(type(page._summary_status))
    )
    assert "Dataset" in visible_text


def test_profile_table_uses_simplified_headers(page):
    table = page._columns_table

    assert table.horizontalHeaderItem(1).text() == "Column"
    assert table.horizontalHeaderItem(2).text() == "Type"
    assert table.horizontalHeaderItem(5).text() == "Blank"
    assert table.horizontalHeaderItem(6).text() == "Complete"
    assert table.horizontalHeaderItem(7).text() == "Distinct"
    assert table.horizontalHeaderItem(8).text() == "Repeated Values"
    assert table.horizontalHeaderItem(9).text() == "Sample"


def test_low_value_profile_columns_are_hidden(page):
    table = page._columns_table

    assert table.isColumnHidden(0)
    assert table.isColumnHidden(3)
    assert table.isColumnHidden(4)
    assert not table.isColumnHidden(1)
    assert not table.isColumnHidden(2)
    assert not table.isColumnHidden(5)
    assert not table.isColumnHidden(6)
    assert not table.isColumnHidden(7)
    assert not table.isColumnHidden(8)
    assert not table.isColumnHidden(9)


def test_column_and_sample_columns_still_stretch(page):
    header = page._columns_table.horizontalHeader()

    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(9) == QHeaderView.ResizeMode.Stretch


@pytest.mark.parametrize(
    ("count", "expected"),
    (
        (1, "1 column"),
        (6, "6 columns"),
        (1200, "1,200 columns"),
    ),
)
def test_column_count_text_uses_natural_pluralisation(count, expected):
    assert DataProfilePage._column_count_text(count) == expected


def test_empty_profile_values_use_real_em_dash():
    assert DataProfilePage._summary_value().text() == "—"
    assert DataProfilePage._format_samples(()) == "—"
