"""Field Mapping page presentation regressions."""

import pytest
from PySide6.QtWidgets import QLabel

from auditor_support_tool.core.workbook_package import FieldMappingStatus
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.field_mapping_page import FieldMappingPage


@pytest.fixture
def page(qtbot):
    widget = FieldMappingPage(workspace_state=WorkspaceState())
    qtbot.addWidget(widget)
    widget.resize(1200, 900)
    widget.show()
    return widget


def test_mapping_uses_auditor_facing_actions(page):
    assert page._reset_button.text() == "Reset Mapping"
    assert page._confirm_button.text() == "Confirm Mapping"
    assert page._continue_button.text() == "Continue to Audit Procedures"


def test_dataset_section_exposes_mapping_progress(page):
    labels = [label.text() for label in page.findChildren(QLabel)]

    assert "Dataset" in labels
    assert "Mapping progress" in labels
    assert page._dataset_progress.text() == "0 of 0 datasets complete"


def test_mapping_table_uses_clear_headers(page):
    table = page._mapping_table

    assert table.horizontalHeaderItem(0).text() == "Prepared Field"
    assert table.horizontalHeaderItem(1).text() == "Type"
    assert table.horizontalHeaderItem(2).text() == "Audit Field"
    assert table.horizontalHeaderItem(3).text() == "What the Audit Field Means"
    assert table.horizontalHeaderItem(4).text() == "Status"


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        (FieldMappingStatus.NOT_STARTED, "Ready to review"),
        (FieldMappingStatus.IN_PROGRESS, "Needs confirmation"),
        (FieldMappingStatus.CONFIRMED, "Ready"),
        (FieldMappingStatus.CONFIRMED_WITH_WARNINGS, "Ready with warnings"),
        (FieldMappingStatus.REVIEW_REQUIRED, "Needs attention"),
        (FieldMappingStatus.NOT_APPLICABLE, "Not applicable"),
    ),
)
def test_dataset_status_labels_are_action_oriented(status, expected):
    assert FieldMappingPage._mapping_status_label(status) == expected


@pytest.mark.parametrize(
    ("status", "mapped", "expected"),
    (
        (FieldMappingStatus.NOT_STARTED, False, "Not mapped"),
        (FieldMappingStatus.IN_PROGRESS, True, "Proposed"),
        (FieldMappingStatus.CONFIRMED, True, "Confirmed"),
        (FieldMappingStatus.CONFIRMED_WITH_WARNINGS, True, "Confirmed"),
        (FieldMappingStatus.NOT_APPLICABLE, False, "Not mapped"),
    ),
)
def test_row_status_does_not_present_provisional_mapping_as_confirmed(
    status,
    mapped,
    expected,
):
    assert FieldMappingPage._row_mapping_status(status, mapped=mapped) == expected


@pytest.mark.parametrize(
    ("complete", "total", "expected"),
    (
        (0, 0, "0 of 0 datasets complete"),
        (0, 1, "0 of 1 dataset complete"),
        (1, 1, "1 of 1 dataset complete"),
        (2, 4, "2 of 4 datasets complete"),
        (4, 4, "4 of 4 datasets complete"),
    ),
)
def test_dataset_progress_text_uses_natural_pluralisation(complete, total, expected):
    assert FieldMappingPage._dataset_progress_text(complete, total) == expected


def test_normal_unfinished_mapping_states_are_not_presented_as_errors():
    not_started_style = FieldMappingPage._mapping_status_badge_style(FieldMappingStatus.NOT_STARTED)
    in_progress_style = FieldMappingPage._mapping_status_badge_style(FieldMappingStatus.IN_PROGRESS)
    attention_style = FieldMappingPage._mapping_status_badge_style(
        FieldMappingStatus.REVIEW_REQUIRED
    )

    assert "#6c757d" in not_started_style
    assert "#6c757d" in in_progress_style
    assert "#c62828" in attention_style


def test_empty_state_points_user_back_to_data_preparation(page):
    assert (
        page._dataset_summary.text()
        == "No dataset is ready for mapping. Complete Data Preparation first."
    )
    assert (
        page._mapping_status.text()
        == "Complete Data Preparation to make a dataset available for mapping."
    )


def test_mapping_dropdown_keeps_used_audit_fields_visible(qtbot):
    from auditor_support_tool.gui.pages.field_mapping_page import NoWheelComboBox

    combo = NoWheelComboBox()
    qtbot.addWidget(combo)

    FieldMappingPage._add_mapping_option(
        combo,
        label="Transaction Date",
        field_key="transaction_date",
    )
    FieldMappingPage._add_mapping_option(
        combo,
        label="Account Code",
        field_key="account_code",
        used_by="Ledger Account",
    )

    assert combo.count() == 2
    assert combo.itemData(0) == "transaction_date"
    assert combo.itemData(1) == "account_code"
    assert combo.itemText(1) == "Account Code — already mapped to Ledger Account"


def test_used_audit_field_is_disabled_in_mapping_dropdown(qtbot):
    from PySide6.QtGui import QStandardItemModel

    from auditor_support_tool.gui.pages.field_mapping_page import NoWheelComboBox

    combo = NoWheelComboBox()
    qtbot.addWidget(combo)

    FieldMappingPage._add_mapping_option(
        combo,
        label="Invoice Number",
        field_key="invoice_number",
        used_by="Vendor Number",
    )

    model = combo.model()
    assert isinstance(model, QStandardItemModel)

    item = model.item(0)
    assert item is not None
    assert not item.isEnabled()
    assert "already mapped to Vendor Number" in item.toolTip()
