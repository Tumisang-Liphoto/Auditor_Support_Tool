"""Data-source selection and population loading page."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.domains.financial_audit.general_ledger.data_import_service import (
    DataImportError,
    DataImportService,
)


class DataSourcesPage(QWidget):
    """Select, inspect and load Excel or CSV audit data."""

    def __init__(
        self,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._import_service = DataImportService()

        self._source_path: Path | None = None

        self._build_interface()
        self._connect_signals()
        self._restore_state()

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

        title = QLabel("Data Sources")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Select an Excel or CSV source file, review its available "
            "worksheets and load the required audit population."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_source_card())
        layout.addWidget(self._build_population_card())
        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_source_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Source File")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Supported file types are Excel workbooks (.xlsx and .xlsm) "
            "and comma-separated value files (.csv)."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        path_label = QLabel("Selected file")
        path_label.setObjectName("fieldLabel")

        self._path_field = QLineEdit()
        self._path_field.setReadOnly(True)
        self._path_field.setPlaceholderText("No source file selected")

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self._browse_button = QPushButton("Select Source File")
        self._browse_button.setObjectName("primaryActionButton")

        self._clear_button = QPushButton("Clear")
        self._clear_button.setObjectName("secondaryActionButton")
        self._clear_button.setEnabled(False)

        button_layout.addWidget(self._browse_button)
        button_layout.addWidget(self._clear_button)
        button_layout.addStretch(1)

        metadata_layout = QGridLayout()
        metadata_layout.setHorizontalSpacing(24)
        metadata_layout.setVerticalSpacing(8)

        file_type_title = QLabel("File type")
        file_type_title.setObjectName("fieldLabel")

        file_size_title = QLabel("File size")
        file_size_title.setObjectName("fieldLabel")

        worksheet_count_title = QLabel("Worksheets")
        worksheet_count_title.setObjectName("fieldLabel")

        self._file_type_value = QLabel("—")
        self._file_type_value.setObjectName("fieldHint")

        self._file_size_value = QLabel("—")
        self._file_size_value.setObjectName("fieldHint")

        self._worksheet_count_value = QLabel("—")
        self._worksheet_count_value.setObjectName("fieldHint")

        metadata_layout.addWidget(file_type_title, 0, 0)
        metadata_layout.addWidget(self._file_type_value, 0, 1)
        metadata_layout.addWidget(file_size_title, 1, 0)
        metadata_layout.addWidget(self._file_size_value, 1, 1)
        metadata_layout.addWidget(worksheet_count_title, 2, 0)
        metadata_layout.addWidget(
            self._worksheet_count_value,
            2,
            1,
        )
        metadata_layout.setColumnStretch(2, 1)

        self._source_status = QLabel("Select a source file to begin.")
        self._source_status.setObjectName("formStatus")
        self._source_status.setProperty("status", "neutral")
        self._source_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(path_label)
        layout.addWidget(self._path_field)
        layout.addLayout(button_layout)
        layout.addLayout(metadata_layout)
        layout.addWidget(self._source_status)

        return card

    def _build_population_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Population")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Choose the worksheet containing the audit population and "
            "load it into the active workspace."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        worksheet_label = QLabel("Worksheet")
        worksheet_label.setObjectName("fieldLabel")

        self._worksheet_combo = QComboBox()
        self._worksheet_combo.setEnabled(False)

        self._worksheet_hint = QLabel(
            "Worksheet information will appear after a source file is selected."
        )
        self._worksheet_hint.setObjectName("fieldHint")
        self._worksheet_hint.setWordWrap(True)

        self._load_button = QPushButton("Load Population")
        self._load_button.setObjectName("primaryActionButton")
        self._load_button.setEnabled(False)

        summary_layout = QGridLayout()
        summary_layout.setHorizontalSpacing(24)
        summary_layout.setVerticalSpacing(8)

        records_title = QLabel("Records loaded")
        records_title.setObjectName("fieldLabel")

        columns_title = QLabel("Source columns")
        columns_title.setObjectName("fieldLabel")

        blank_rows_title = QLabel("Blank rows skipped")
        blank_rows_title.setObjectName("fieldLabel")

        source_rows_title = QLabel("Source records read")
        source_rows_title.setObjectName("fieldLabel")

        self._records_value = QLabel("—")
        self._records_value.setObjectName("fieldHint")

        self._columns_value = QLabel("—")
        self._columns_value.setObjectName("fieldHint")

        self._blank_rows_value = QLabel("—")
        self._blank_rows_value.setObjectName("fieldHint")

        self._source_rows_value = QLabel("—")
        self._source_rows_value.setObjectName("fieldHint")

        summary_layout.addWidget(records_title, 0, 0)
        summary_layout.addWidget(self._records_value, 0, 1)
        summary_layout.addWidget(columns_title, 1, 0)
        summary_layout.addWidget(self._columns_value, 1, 1)
        summary_layout.addWidget(blank_rows_title, 2, 0)
        summary_layout.addWidget(
            self._blank_rows_value,
            2,
            1,
        )
        summary_layout.addWidget(source_rows_title, 3, 0)
        summary_layout.addWidget(
            self._source_rows_value,
            3,
            1,
        )
        summary_layout.setColumnStretch(2, 1)

        self._population_status = QLabel("No population is loaded.")
        self._population_status.setObjectName("formStatus")
        self._population_status.setProperty(
            "status",
            "neutral",
        )
        self._population_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(worksheet_label)
        layout.addWidget(self._worksheet_combo)
        layout.addWidget(self._worksheet_hint)
        layout.addWidget(
            self._load_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addLayout(summary_layout)
        layout.addWidget(self._population_status)

        return card

    def _connect_signals(self) -> None:
        self._browse_button.clicked.connect(self._select_source_file)
        self._clear_button.clicked.connect(self._clear_workspace)
        self._load_button.clicked.connect(self._load_population)
        self._worksheet_combo.currentIndexChanged.connect(self._update_worksheet_hint)

    def _select_source_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audit Data Source",
            str(Path.home()),
            (
                "Supported Data Files (*.xlsx *.xlsm *.csv);;"
                "Excel Workbooks (*.xlsx *.xlsm);;"
                "CSV Files (*.csv)"
            ),
        )

        if not selected_path:
            return

        path = Path(selected_path)

        try:
            source_info = self._import_service.inspect_source(path)
        except DataImportError as error:
            self._set_source_status(
                str(error),
                "error",
            )
            return

        self._source_path = source_info.path
        self._workspace_state.set_source(source_info)

        self._path_field.setText(str(source_info.path))
        self._file_type_value.setText(source_info.file_type.upper())
        self._file_size_value.setText(self._format_file_size(source_info.file_size_bytes))
        self._worksheet_count_value.setText(str(len(source_info.worksheets)))

        self._worksheet_combo.clear()

        for worksheet in source_info.worksheets:
            self._worksheet_combo.addItem(
                worksheet.name,
                worksheet,
            )

        self._worksheet_combo.setEnabled(True)
        self._load_button.setEnabled(True)
        self._clear_button.setEnabled(True)

        self._reset_population_summary()
        self._update_worksheet_hint()

        self._set_source_status(
            "Source file inspected successfully.",
            "success",
        )
        self._set_population_status(
            "Select a worksheet and load the population.",
            "neutral",
        )

    def _load_population(self) -> None:
        if self._source_path is None:
            self._set_population_status(
                "Select a source file before loading a population.",
                "error",
            )
            return

        worksheet_name = self._worksheet_combo.currentText().strip()

        if not worksheet_name:
            self._set_population_status(
                "Select a worksheet before loading the population.",
                "error",
            )
            return

        self._load_button.setEnabled(False)
        self._load_button.setText("Loading…")

        try:
            table = self._import_service.load_table(
                self._source_path,
                worksheet_name=worksheet_name,
            )
        except DataImportError as error:
            self._set_population_status(
                str(error),
                "error",
            )
            return
        finally:
            self._load_button.setText("Load Population")
            self._load_button.setEnabled(True)

        self._workspace_state.set_loaded_table(table)

        self._records_value.setText(f"{table.record_count:,}")
        self._columns_value.setText(f"{table.column_count:,}")
        self._blank_rows_value.setText(f"{table.summary.blank_rows_skipped:,}")
        self._source_rows_value.setText(f"{table.summary.source_records_read:,}")

        self._set_population_status(
            (f"Population loaded successfully from '{table.worksheet_name}'."),
            "success",
        )

    def _update_worksheet_hint(self) -> None:
        worksheet = self._worksheet_combo.currentData()

        if worksheet is None:
            self._worksheet_hint.setText(
                "Worksheet information will appear after a source file is selected."
            )
            return

        self._worksheet_hint.setText(
            
                f"Estimated data rows: "
                f"{worksheet.estimated_data_rows:,} | "
                f"Maximum columns: {worksheet.maximum_column:,}"
            
        )

    def _clear_workspace(self) -> None:
        self._workspace_state.clear()
        self._source_path = None

        self._path_field.clear()
        self._file_type_value.setText("—")
        self._file_size_value.setText("—")
        self._worksheet_count_value.setText("—")

        self._worksheet_combo.clear()
        self._worksheet_combo.setEnabled(False)

        self._load_button.setEnabled(False)
        self._clear_button.setEnabled(False)

        self._reset_population_summary()

        self._set_source_status(
            "Select a source file to begin.",
            "neutral",
        )
        self._set_population_status(
            "No population is loaded.",
            "neutral",
        )

    def _restore_state(self) -> None:
        source_info = self._workspace_state.source_info

        if source_info is None:
            return

        self._source_path = source_info.path
        self._path_field.setText(str(source_info.path))
        self._file_type_value.setText(source_info.file_type.upper())
        self._file_size_value.setText(self._format_file_size(source_info.file_size_bytes))
        self._worksheet_count_value.setText(str(len(source_info.worksheets)))

        self._worksheet_combo.clear()

        for worksheet in source_info.worksheets:
            self._worksheet_combo.addItem(
                worksheet.name,
                worksheet,
            )

        self._worksheet_combo.setEnabled(True)
        self._load_button.setEnabled(True)
        self._clear_button.setEnabled(True)

        loaded_table = self._workspace_state.loaded_table

        if loaded_table is not None:
            worksheet_index = self._worksheet_combo.findText(loaded_table.worksheet_name)

            if worksheet_index >= 0:
                self._worksheet_combo.setCurrentIndex(worksheet_index)

            self._records_value.setText(f"{loaded_table.record_count:,}")
            self._columns_value.setText(f"{loaded_table.column_count:,}")
            self._blank_rows_value.setText(f"{loaded_table.summary.blank_rows_skipped:,}")
            self._source_rows_value.setText(f"{loaded_table.summary.source_records_read:,}")

            self._set_population_status(
                (f"Population loaded from '{loaded_table.worksheet_name}'."),
                "success",
            )

        self._update_worksheet_hint()

    def _reset_population_summary(self) -> None:
        self._records_value.setText("—")
        self._columns_value.setText("—")
        self._blank_rows_value.setText("—")
        self._source_rows_value.setText("—")

    def _set_source_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._source_status.setText(message)
        self._source_status.setProperty("status", status)
        self._refresh_status_style(self._source_status)

    def _set_population_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._population_status.setText(message)
        self._population_status.setProperty("status", status)
        self._refresh_status_style(self._population_status)

    @staticmethod
    def _refresh_status_style(label: QLabel) -> None:
        label.style().unpolish(label)
        label.style().polish(label)

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        size = float(size_bytes)

        for unit in (
            "bytes",
            "KB",
            "MB",
            "GB",
        ):
            if size < 1024 or unit == "GB":
                if unit == "bytes":
                    return f"{int(size):,} {unit}"

                return f"{size:,.2f} {unit}"

            size /= 1024

        return f"{size_bytes:,} bytes"
