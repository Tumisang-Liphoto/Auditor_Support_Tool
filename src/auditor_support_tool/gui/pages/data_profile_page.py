"""Read-only page for reviewing loaded audit dataset profiles."""

from datetime import date, datetime
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
)
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    ColumnProfile,
    DataProfile,
)


class DataProfilePage(QWidget):
    """Display structural and quality information for datasets."""

    continue_requested = Signal(str)

    def __init__(
        self,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._updating_dataset_selector = False

        self._build_interface()
        self._connect_signals()
        self._refresh_page()

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Data Profile")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Review the structure, completeness and basic "
            "characteristics of each confirmed dataset."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_summary_card())
        layout.addWidget(self._build_columns_card())
        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_summary_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Population Summary")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "This page describes the selected dataset. "
            "It does not modify data, map columns or run "
            "audit tests."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        dataset_label = QLabel("Dataset being reviewed")
        dataset_label.setObjectName("fieldLabel")

        self._dataset_selector = QComboBox()
        self._dataset_selector.setEnabled(False)

        self._dataset_selector_hint = QLabel(
            "Only datasets included and confirmed in Data Sources are available here."
        )
        self._dataset_selector_hint.setObjectName("fieldHint")
        self._dataset_selector_hint.setWordWrap(True)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(28)
        summary_grid.setVerticalSpacing(10)

        self._source_file_value = self._summary_value()
        self._worksheet_value = self._summary_value()
        self._dataset_name_value = self._summary_value()
        self._dataset_type_value = self._summary_value()
        self._records_value = self._summary_value()
        self._columns_value = self._summary_value()
        self._blank_cells_value = self._summary_value()
        self._columns_with_blanks_value = self._summary_value()

        summary_items = (
            ("Source file", self._source_file_value),
            (
                "Original worksheet",
                self._worksheet_value,
            ),
            (
                "Confirmed dataset name",
                self._dataset_name_value,
            ),
            (
                "Confirmed dataset type",
                self._dataset_type_value,
            ),
            ("Records", self._records_value),
            ("Columns", self._columns_value),
            (
                "Blank cells",
                self._blank_cells_value,
            ),
            (
                "Columns containing blanks",
                self._columns_with_blanks_value,
            ),
        )

        for row_number, (
            label_text,
            value_label,
        ) in enumerate(summary_items):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")

            summary_grid.addWidget(
                label,
                row_number,
                0,
            )
            summary_grid.addWidget(
                value_label,
                row_number,
                1,
            )

        summary_grid.setColumnStretch(2, 1)

        self._summary_status = QLabel(
            "Confirm datasets in Data Sources before reviewing their profiles."
        )
        self._summary_status.setObjectName("formStatus")
        self._summary_status.setProperty(
            "status",
            "neutral",
        )
        self._summary_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(dataset_label)
        layout.addWidget(self._dataset_selector)
        layout.addWidget(self._dataset_selector_hint)
        layout.addLayout(summary_grid)
        layout.addWidget(self._summary_status)

        return card

    def _build_columns_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Source Columns")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Each row represents a source column from the "
            "selected dataset. Detected types and statistics "
            "are informational at this stage."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._columns_table = QTableWidget()
        self._columns_table.setColumnCount(10)
        self._columns_table.setHorizontalHeaderLabels(
            (
                "Position",
                "Column",
                "Detected Type",
                "Records",
                "Populated",
                "Blank",
                "Complete",
                "Distinct",
                "Duplicate Values",
                "Sample Values",
            )
        )

        self._columns_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._columns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._columns_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._columns_table.setAlternatingRowColors(True)
        self._columns_table.setSortingEnabled(True)
        self._columns_table.verticalHeader().setVisible(False)
        self._columns_table.setMinimumHeight(360)

        header = self._columns_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            9,
            QHeaderView.ResizeMode.Stretch,
        )

        self._table_status = QLabel("No confirmed dataset is available.")
        self._table_status.setObjectName("fieldHint")
        self._table_status.setWordWrap(True)

        actions_layout = QHBoxLayout()
        actions_layout.addStretch(1)

        self._continue_button = QPushButton("Confirm Profiles and Continue")
        self._continue_button.setObjectName("primaryActionButton")
        self._continue_button.setEnabled(False)

        actions_layout.addWidget(self._continue_button)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._columns_table)
        layout.addWidget(self._table_status)
        layout.addLayout(actions_layout)

        return card

    def _connect_signals(self) -> None:
        self._dataset_selector.currentIndexChanged.connect(self._dataset_selection_changed)
        self._continue_button.clicked.connect(self._continue_to_data_preparation)

        self._workspace_state.source_changed.connect(self._refresh_page)
        self._workspace_state.population_loaded.connect(self._refresh_page)
        self._workspace_state.profile_created.connect(self._refresh_page)
        self._workspace_state.workbook_package_changed.connect(self._refresh_page)
        self._workspace_state.active_dataset_changed.connect(self._refresh_page)
        self._workspace_state.workspace_cleared.connect(self._refresh_page)

    def _refresh_dataset_selector(self) -> None:
        selected_datasets = self._workspace_state.selected_datasets
        active_dataset_id = self._workspace_state.active_dataset_id

        confirmed_datasets = tuple(
            dataset
            for dataset in selected_datasets
            if (dataset.status == PreparationStatus.CONFIRMED)
        )

        self._updating_dataset_selector = True

        try:
            self._dataset_selector.clear()

            for dataset in confirmed_datasets:
                self._dataset_selector.addItem(
                    dataset.confirmed_display_name,
                    dataset.dataset_id,
                )

            self._dataset_selector.setEnabled(self._dataset_selector.count() > 0)

            active_index = self._dataset_selector.findData(active_dataset_id)

            if active_index >= 0:
                self._dataset_selector.setCurrentIndex(active_index)
            elif self._dataset_selector.count() > 0:
                self._dataset_selector.setCurrentIndex(0)
        finally:
            self._updating_dataset_selector = False

    def _dataset_selection_changed(
        self,
        index: int,
    ) -> None:
        if self._updating_dataset_selector or index < 0:
            return

        dataset_id = self._dataset_selector.itemData(index)

        if not isinstance(dataset_id, str):
            return

        try:
            self._workspace_state.set_active_dataset(dataset_id)
        except ValueError as error:
            self._set_summary_status(
                str(error),
                "error",
            )

    def _refresh_page(self) -> None:
        self._refresh_dataset_selector()
        self._continue_button.setEnabled(False)

        active_dataset = self._workspace_state.active_dataset

        if active_dataset is None or active_dataset.status != PreparationStatus.CONFIRMED:
            self._clear_summary()
            self._columns_table.setRowCount(0)

            self._set_summary_status(
                ("Confirm at least one dataset in Data Sources before reviewing its profile."),
                "neutral",
            )
            self._table_status.setText("No confirmed dataset is available.")
            return

        table = active_dataset.loaded_table
        profile = active_dataset.data_profile

        if profile is None:
            self._source_file_value.setText(table.source_path.name)
            self._worksheet_value.setText(active_dataset.original_worksheet_name)
            self._dataset_name_value.setText(active_dataset.confirmed_display_name)
            self._dataset_type_value.setText(
                self._dataset_type_label(active_dataset.confirmed_dataset_type.value)
            )
            self._records_value.setText(f"{table.record_count:,}")
            self._columns_value.setText(f"{table.column_count:,}")
            self._blank_cells_value.setText("—")
            self._columns_with_blanks_value.setText("—")
            self._columns_table.setRowCount(0)

            self._set_summary_status(
                (
                    "No profile is available for this "
                    "dataset. Return to Data Sources and "
                    "reload the workbook."
                ),
                "error",
            )
            self._table_status.setText("The dataset profile could not be displayed.")
            return

        self._display_profile(
            profile=profile,
            dataset_name=(active_dataset.confirmed_display_name),
            dataset_type=(active_dataset.confirmed_dataset_type.value),
            original_worksheet_name=(active_dataset.original_worksheet_name),
        )
        self._continue_button.setEnabled(self._all_confirmed_profiles_available())

    def _continue_to_data_preparation(self) -> None:
        """Confirm profile availability and open Data Preparation."""

        missing_profiles = tuple(
            dataset.confirmed_display_name
            for dataset in self._workspace_state.selected_datasets
            if (dataset.status == PreparationStatus.CONFIRMED and dataset.data_profile is None)
        )

        if missing_profiles:
            self._set_summary_status(
                (
                    "A profile is not available for: "
                    f"{', '.join(missing_profiles)}. "
                    "Reload the workbook in Data Sources."
                ),
                "error",
            )
            return

        if not self._all_confirmed_profiles_available():
            self._set_summary_status(
                ("Confirm at least one dataset in Data Sources before continuing."),
                "error",
            )
            return

        self.continue_requested.emit("workspace.data_preparation")

    def _all_confirmed_profiles_available(self) -> bool:
        """Return whether all selected confirmed datasets have profiles."""

        datasets = tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.status == PreparationStatus.CONFIRMED
        )

        return bool(datasets) and all(dataset.data_profile is not None for dataset in datasets)

    def _display_profile(
        self,
        profile: DataProfile,
        dataset_name: str,
        dataset_type: str,
        original_worksheet_name: str,
    ) -> None:
        self._source_file_value.setText(profile.source_file)
        self._worksheet_value.setText(original_worksheet_name)
        self._dataset_name_value.setText(dataset_name)
        self._dataset_type_value.setText(self._dataset_type_label(dataset_type))
        self._records_value.setText(f"{profile.record_count:,}")
        self._columns_value.setText(f"{profile.column_count:,}")
        self._blank_cells_value.setText(f"{profile.blank_cell_count:,}")
        self._columns_with_blanks_value.setText(f"{profile.columns_with_blanks:,}")

        self._columns_table.setSortingEnabled(False)
        self._columns_table.setRowCount(len(profile.columns))

        for row_number, column in enumerate(profile.columns):
            self._populate_column_row(
                row_number,
                column,
            )

        self._columns_table.setSortingEnabled(True)

        self._set_summary_status(
            ("The selected dataset profile is available."),
            "success",
        )

        self._table_status.setText(
            
                f"{len(profile.columns):,} source "
                "column(s) were profiled. No audit "
                "tests have been run."
            
        )

    def _populate_column_row(
        self,
        row_number: int,
        column: ColumnProfile,
    ) -> None:
        values = (
            str(column.position),
            column.column_name,
            self._dataset_type_label(column.detected_type.value),
            f"{column.total_records:,}",
            f"{column.populated_records:,}",
            f"{column.blank_records:,}",
            (f"{column.completeness_percentage:.2f}%"),
            f"{column.distinct_values:,}",
            f"{column.duplicate_values:,}",
            self._format_samples(column.sample_values),
        )

        numeric_columns = {
            0,
            3,
            4,
            5,
            6,
            7,
            8,
        }

        for column_number, value in enumerate(values):
            item = QTableWidgetItem(value)

            if column_number in numeric_columns:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self._columns_table.setItem(
                row_number,
                column_number,
                item,
            )

    def _clear_summary(self) -> None:
        for label in (
            self._source_file_value,
            self._worksheet_value,
            self._dataset_name_value,
            self._dataset_type_value,
            self._records_value,
            self._columns_value,
            self._blank_cells_value,
            self._columns_with_blanks_value,
        ):
            label.setText("—")

    def _set_summary_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._summary_status.setText(message)
        self._summary_status.setProperty(
            "status",
            status,
        )

        self._summary_status.style().unpolish(self._summary_status)
        self._summary_status.style().polish(self._summary_status)

    @staticmethod
    def _summary_value() -> QLabel:
        label = QLabel("—")
        label.setObjectName("fieldHint")
        return label

    @staticmethod
    def _dataset_type_label(
        value: str,
    ) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def _format_samples(
        values: tuple[Any, ...],
    ) -> str:
        if not values:
            return "—"

        return " | ".join(DataProfilePage._format_value(value) for value in values)

    @staticmethod
    def _format_value(
        value: Any,
    ) -> str:
        if isinstance(value, datetime):
            return value.isoformat(
                sep=" ",
                timespec="seconds",
            )

        if isinstance(value, date):
            return value.isoformat()

        return str(value)
