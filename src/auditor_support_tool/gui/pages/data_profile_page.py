"""GUI page for reviewing the profile of received audit data."""

from datetime import date, datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
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

from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    ColumnProfile,
    DataProfile,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_service import (
    DataProfileService,
)


class DataProfilePage(QWidget):
    """Display structural and quality information about received data."""

    def __init__(
        self,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._profile_service = DataProfileService()

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
            "Review the structure, completeness and basic characteristics "
            "of the population received from the auditee."
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
            "This summary describes the currently loaded worksheet. "
            "It does not assess or execute any audit test."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(28)
        summary_grid.setVerticalSpacing(10)

        self._source_file_value = self._summary_value()
        self._worksheet_value = self._summary_value()
        self._records_value = self._summary_value()
        self._columns_value = self._summary_value()
        self._blank_cells_value = self._summary_value()
        self._columns_with_blanks_value = self._summary_value()

        summary_items = (
            ("Source file", self._source_file_value),
            ("Worksheet", self._worksheet_value),
            ("Records", self._records_value),
            ("Columns", self._columns_value),
            ("Blank cells", self._blank_cells_value),
            (
                "Columns containing blanks",
                self._columns_with_blanks_value,
            ),
        )

        for row_number, (label_text, value_label) in enumerate(summary_items):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")

            summary_grid.addWidget(label, row_number, 0)
            summary_grid.addWidget(value_label, row_number, 1)

        summary_grid.setColumnStretch(2, 1)

        self._generate_button = QPushButton("Generate Data Profile")
        self._generate_button.setObjectName("primaryActionButton")
        self._generate_button.setEnabled(False)

        self._summary_status = QLabel(
            "Load a population from Data Sources before generating a profile."
        )
        self._summary_status.setObjectName("formStatus")
        self._summary_status.setProperty("status", "neutral")
        self._summary_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addLayout(summary_grid)
        layout.addWidget(
            self._generate_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
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
            "Each row below represents a column exactly as received in "
            "the selected source worksheet."
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

        self._columns_table.setMinimumHeight(360)

        self._table_status = QLabel("No data profile is available.")
        self._table_status.setObjectName("fieldHint")
        self._table_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._columns_table)
        layout.addWidget(self._table_status)

        return card

    def _connect_signals(self) -> None:
        self._generate_button.clicked.connect(self._generate_profile)

        self._workspace_state.source_changed.connect(self._refresh_page)
        self._workspace_state.population_loaded.connect(self._refresh_page)
        self._workspace_state.profile_created.connect(self._refresh_page)
        self._workspace_state.workspace_cleared.connect(self._refresh_page)

    def _generate_profile(self) -> None:
        table = self._workspace_state.loaded_table

        if table is None:
            self._set_summary_status(
                "No population is loaded.",
                "error",
            )
            return

        self._generate_button.setEnabled(False)
        self._generate_button.setText("Profiling…")

        try:
            profile = self._profile_service.profile(table)
            self._workspace_state.set_data_profile(profile)
        except (TypeError, ValueError) as error:
            self._set_summary_status(
                f"Unable to generate the data profile: {error}",
                "error",
            )
        finally:
            self._generate_button.setText("Generate Data Profile")
            self._generate_button.setEnabled(self._workspace_state.has_loaded_population)

    def _refresh_page(self) -> None:
        table = self._workspace_state.loaded_table
        profile = self._workspace_state.data_profile

        self._generate_button.setEnabled(table is not None)

        if table is None:
            self._clear_summary()
            self._columns_table.setRowCount(0)

            self._set_summary_status(
                ("Load a population from Data Sources before generating a profile."),
                "neutral",
            )
            self._table_status.setText("No data profile is available.")
            return

        self._source_file_value.setText(table.source_path.name)
        self._worksheet_value.setText(table.worksheet_name)
        self._records_value.setText(f"{table.record_count:,}")
        self._columns_value.setText(f"{table.column_count:,}")

        if profile is None:
            self._blank_cells_value.setText("—")
            self._columns_with_blanks_value.setText("—")
            self._columns_table.setRowCount(0)

            self._set_summary_status(
                ("The population is loaded. Generate its profile to review the received columns."),
                "neutral",
            )
            self._table_status.setText("The data profile has not yet been generated.")
            return

        self._display_profile(profile)

    def _display_profile(
        self,
        profile: DataProfile,
    ) -> None:
        self._source_file_value.setText(profile.source_file)
        self._worksheet_value.setText(profile.worksheet_name)
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
            "The data profile was generated successfully.",
            "success",
        )

        self._table_status.setText(
            
                f"{len(profile.columns):,} source columns were "
                "profiled. No audit tests have been assessed."
            
        )

    def _populate_column_row(
        self,
        row_number: int,
        column: ColumnProfile,
    ) -> None:
        values = (
            str(column.position),
            column.column_name,
            column.detected_type.value.title(),
            f"{column.total_records:,}",
            f"{column.populated_records:,}",
            f"{column.blank_records:,}",
            f"{column.completeness_percentage:.2f}%",
            f"{column.distinct_values:,}",
            f"{column.duplicate_values:,}",
            self._format_samples(column.sample_values),
        )

        for column_number, value in enumerate(values):
            item = QTableWidgetItem(value)

            if column_number in {
                0,
                3,
                4,
                5,
                6,
                7,
                8,
            }:
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
        self._summary_status.setProperty("status", status)

        self._summary_status.style().unpolish(self._summary_status)
        self._summary_status.style().polish(self._summary_status)

    @staticmethod
    def _summary_value() -> QLabel:
        label = QLabel("—")
        label.setObjectName("fieldHint")
        return label

    @staticmethod
    def _format_samples(
        values: tuple[Any, ...],
    ) -> str:
        if not values:
            return "—"

        return " | ".join(DataProfilePage._format_value(value) for value in values)

    @staticmethod
    def _format_value(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat(
                sep=" ",
                timespec="seconds",
            )

        if isinstance(value, date):
            return value.isoformat()

        return str(value)
