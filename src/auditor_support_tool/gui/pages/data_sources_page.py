"""Power BI-style navigator for workbook audit data sources."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.data_import_service import (
    DataImportError,
    DataImportService,
)
from auditor_support_tool.core.workbook_package import (
    DatasetType,
    PreparationStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.core.workbook_suggestion_service import (
    WorkbookSuggestionService,
)
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SourceFileInfo,
)


class DataSourcesPage(QWidget):
    """Inspect a source file and select its worksheet datasets."""

    continue_requested = Signal(str)
    clear_requested = Signal()

    def __init__(
        self,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._import_service = DataImportService()
        self._package_service = WorkbookPackageService()
        self._suggestion_service = WorkbookSuggestionService()

        self._source_path: Path | None = None
        self._updating_navigator = False

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
            "Select a workbook, load its available worksheets and choose "
            "the datasets that will form part of the current audit."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_source_card())
        layout.addWidget(self._build_navigator_card())
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

        heading = QLabel("Select File")
        heading.setObjectName("profileSectionTitle")

        description = QLabel("Select an Excel workbook or CSV file, then load its data.")
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        path_label = QLabel("Selected file")
        path_label.setObjectName("fieldLabel")

        self._path_field = QLineEdit()
        self._path_field.setReadOnly(True)
        self._path_field.setPlaceholderText("No file selected")

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self._browse_button = QPushButton("Select File")
        self._browse_button.setObjectName("primaryActionButton")

        self._load_package_button = QPushButton("Load Data")
        self._load_package_button.setObjectName("primaryActionButton")
        self._load_package_button.setEnabled(False)

        self._clear_button = QPushButton("Clear Audit")
        self._clear_button.setObjectName("secondaryActionButton")
        self._clear_button.setEnabled(False)
        self._clear_button.setVisible(False)

        button_layout.addWidget(self._browse_button)
        button_layout.addWidget(self._load_package_button)
        button_layout.addWidget(self._clear_button)
        button_layout.addStretch(1)

        metadata_layout = QGridLayout()
        metadata_layout.setHorizontalSpacing(24)
        metadata_layout.setVerticalSpacing(8)

        self._file_type_value = self._metadata_value()
        self._file_size_value = self._metadata_value()
        self._worksheet_count_value = self._metadata_value()
        self._loaded_dataset_count_value = self._metadata_value()

        metadata_items = (
            ("File type", self._file_type_value),
            ("File size", self._file_size_value),
            (
                "Available worksheets",
                self._worksheet_count_value,
            ),
            (
                "Loaded datasets",
                self._loaded_dataset_count_value,
            ),
        )

        for row_number, (
            label_text,
            value_label,
        ) in enumerate(metadata_items):
            label = QLabel(label_text)
            label.setObjectName("fieldLabel")

            metadata_layout.addWidget(
                label,
                row_number,
                0,
            )
            metadata_layout.addWidget(
                value_label,
                row_number,
                1,
            )

        metadata_layout.setColumnStretch(2, 1)

        self._source_status = QLabel("Select a source file to begin.")
        self._source_status.setObjectName("formStatus")
        self._source_status.setProperty(
            "status",
            "neutral",
        )
        self._source_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(path_label)
        layout.addWidget(self._path_field)
        layout.addLayout(button_layout)
        layout.addLayout(metadata_layout)
        layout.addWidget(self._source_status)

        return card

    def _build_navigator_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Select Data to Include")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Choose the datasets for this audit. Review the dataset name and type "
            "before continuing."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._navigator_table = QTableWidget()
        self._navigator_table.setColumnCount(8)
        self._navigator_table.setHorizontalHeaderLabels(
            (
                "Include",
                "Source",
                "Dataset Name",
                "Dataset Type",
                "Records",
                "Columns",
                "Suggestion Confidence",
                "Status",
            )
        )
        # Confidence and preparation status remain part of the internal workbook
        # model, but they are implementation details at this stage of the workflow.
        self._navigator_table.setColumnHidden(6, True)
        self._navigator_table.setColumnHidden(7, True)
        self._navigator_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._navigator_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._navigator_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._navigator_table.setAlternatingRowColors(True)
        self._navigator_table.verticalHeader().setVisible(False)
        self._navigator_table.setMinimumHeight(330)

        header = self._navigator_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self._select_all_button = QPushButton("Select All")
        self._select_all_button.setObjectName("secondaryActionButton")
        self._select_all_button.setEnabled(False)

        self._exclude_all_button = QPushButton("Clear Selection")
        self._exclude_all_button.setObjectName("secondaryActionButton")
        self._exclude_all_button.setEnabled(False)

        self._confirm_button = QPushButton("Continue to Data Profile")
        self._confirm_button.setObjectName("primaryActionButton")
        self._confirm_button.setEnabled(False)

        actions_layout.addWidget(self._select_all_button)
        actions_layout.addWidget(self._exclude_all_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._confirm_button)

        self._navigator_status = QLabel("Select a source file to view its worksheets.")
        self._navigator_status.setObjectName("formStatus")
        self._navigator_status.setProperty(
            "status",
            "neutral",
        )
        self._navigator_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._navigator_table)
        layout.addLayout(actions_layout)
        layout.addWidget(self._navigator_status)

        return card

    def _connect_signals(self) -> None:
        self._browse_button.clicked.connect(self._select_source_file)
        self._load_package_button.clicked.connect(self._load_workbook_package)
        self._clear_button.clicked.connect(self._clear_workspace)
        self._select_all_button.clicked.connect(self._include_all_datasets)
        self._exclude_all_button.clicked.connect(self._exclude_all_datasets)
        self._confirm_button.clicked.connect(self._confirm_and_continue)

        self._navigator_table.itemChanged.connect(self._navigator_item_changed)
        self._navigator_table.itemSelectionChanged.connect(self._navigator_selection_changed)

        self._workspace_state.workbook_package_changed.connect(self._refresh_loaded_package)
        self._workspace_state.active_dataset_changed.connect(self._select_active_dataset_row)
        self._workspace_state.workspace_cleared.connect(self._reset_page)

    def _select_source_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audit Data Source",
            str(Path.home()),
            (
                "Supported Data Files "
                "(*.xlsx *.xlsm *.csv);;"
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

        self._display_source_metadata(source_info)
        self._display_inspected_worksheets(source_info)

        self._set_load_button_mode(reload=False)
        self._load_package_button.setEnabled(True)
        self._clear_button.setEnabled(True)
        self._select_all_button.setEnabled(False)
        self._exclude_all_button.setEnabled(False)
        self._confirm_button.setEnabled(False)

        self._set_source_status(
            "File selected and ready to load.",
            "success",
        )
        self._set_navigator_status(
            (
                f"{len(source_info.worksheets):,} source "
                "item(s) found. Load the data to review dataset "
                "names and types."
            ),
            "neutral",
        )

    def _display_inspected_worksheets(
        self,
        source_info: SourceFileInfo,
    ) -> None:
        self._updating_navigator = True

        try:
            self._navigator_table.clearContents()
            self._navigator_table.setRowCount(len(source_info.worksheets))

            for row_number, worksheet in enumerate(source_info.worksheets):
                include_item = QTableWidgetItem()
                include_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                include_item.setCheckState(
                    Qt.CheckState.Checked
                    if worksheet.estimated_data_rows > 0
                    else Qt.CheckState.Unchecked
                )

                include_item.setData(
                    Qt.ItemDataRole.UserRole,
                    worksheet.name,
                )

                worksheet_item = QTableWidgetItem(worksheet.name)
                suggested_name_item = QTableWidgetItem("Not analysed")
                dataset_type_item = QTableWidgetItem("Not analysed")
                records_item = self._centred_item(f"{worksheet.estimated_data_rows:,}")
                columns_item = self._centred_item(f"{worksheet.maximum_column:,}")
                confidence_item = self._centred_item("—")

                status_text = "Ready for analysis" if worksheet.estimated_data_rows > 0 else "Empty"
                status_item = self._centred_item(status_text)

                self._navigator_table.setItem(
                    row_number,
                    0,
                    include_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    1,
                    worksheet_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    2,
                    suggested_name_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    3,
                    dataset_type_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    4,
                    records_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    5,
                    columns_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    6,
                    confidence_item,
                )
                self._navigator_table.setItem(
                    row_number,
                    7,
                    status_item,
                )
        finally:
            self._updating_navigator = False

    def _load_workbook_package(self) -> None:
        if self._source_path is None:
            self._set_navigator_status(
                ("Select a file before loading data."),
                "error",
            )
            return

        was_reload = self._load_package_button.text() == "Reload Data"

        self._load_package_button.setEnabled(False)
        self._load_package_button.setText("Loading…")

        try:
            package = self._package_service.build_package(self._source_path)
        except (
            DataImportError,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            self._set_load_button_mode(reload=was_reload)
            self._load_package_button.setEnabled(True)
            self._set_navigator_status(
                (f"Unable to load data: {error}"),
                "error",
            )
            return

        if not package.datasets:
            self._set_load_button_mode(reload=was_reload)
            self._load_package_button.setEnabled(True)
            self._set_navigator_status(
                ("No non-empty datasets were found in the selected source."),
                "error",
            )
            return

        self._load_package_button.setEnabled(True)

        self._workspace_state.set_workbook_package(package)

        self._set_load_button_mode(reload=True)
        self._set_source_status("", "neutral")
        self._set_navigator_status(
            (
                f"{self._dataset_count_text(len(package.datasets))} available. "
                "Review which datasets to include, their names and types, then continue."
            ),
            "neutral",
        )

    def _refresh_loaded_package(self) -> None:
        package = self._workspace_state.workbook_package

        if package is None:
            return

        self._updating_navigator = True

        try:
            self._navigator_table.clearContents()
            self._navigator_table.setRowCount(len(package.datasets))

            for row_number, dataset in enumerate(package.datasets):
                self._populate_dataset_row(
                    row_number,
                    dataset,
                )
        finally:
            self._updating_navigator = False

        self._loaded_dataset_count_value.setText(f"{len(package.datasets):,}")

        has_datasets = bool(package.datasets)

        self._select_all_button.setEnabled(has_datasets)
        self._exclude_all_button.setEnabled(has_datasets)
        self._confirm_button.setEnabled(has_datasets)

        self._select_active_dataset_row()

    def _populate_dataset_row(
        self,
        row_number: int,
        dataset: WorksheetDataset,
    ) -> None:
        include_item = QTableWidgetItem()
        include_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        include_item.setCheckState(
            Qt.CheckState.Checked if dataset.selected else Qt.CheckState.Unchecked
        )
        include_item.setData(
            Qt.ItemDataRole.UserRole,
            dataset.dataset_id,
        )

        worksheet_item = QTableWidgetItem(dataset.original_worksheet_name)
        worksheet_item.setData(
            Qt.ItemDataRole.UserRole,
            dataset.dataset_id,
        )

        name_editor = QLineEdit(dataset.confirmed_display_name)
        name_editor.setProperty(
            "dataset_id",
            dataset.dataset_id,
        )
        name_editor.editingFinished.connect(self._dataset_name_changed)

        type_combo = QComboBox()
        type_combo.setProperty(
            "dataset_id",
            dataset.dataset_id,
        )

        for dataset_type in DatasetType:
            type_combo.addItem(
                self._suggestion_service.dataset_type_label(dataset_type),
                dataset_type,
            )

        type_index = type_combo.findData(dataset.confirmed_dataset_type)

        if type_index >= 0:
            type_combo.setCurrentIndex(type_index)

        type_combo.currentIndexChanged.connect(self._dataset_type_changed)

        records_item = self._centred_item(f"{dataset.record_count:,}")
        columns_item = self._centred_item(f"{dataset.column_count:,}")
        confidence_item = self._centred_item(dataset.suggestion_confidence.value.title())
        status_item = self._centred_item(self._status_label(dataset.status))

        self._navigator_table.setItem(
            row_number,
            0,
            include_item,
        )
        self._navigator_table.setItem(
            row_number,
            1,
            worksheet_item,
        )
        self._navigator_table.setCellWidget(
            row_number,
            2,
            name_editor,
        )
        self._navigator_table.setCellWidget(
            row_number,
            3,
            type_combo,
        )
        self._navigator_table.setItem(
            row_number,
            4,
            records_item,
        )
        self._navigator_table.setItem(
            row_number,
            5,
            columns_item,
        )
        self._navigator_table.setItem(
            row_number,
            6,
            confidence_item,
        )
        self._navigator_table.setItem(
            row_number,
            7,
            status_item,
        )

    def _navigator_item_changed(
        self,
        item: QTableWidgetItem,
    ) -> None:
        if self._updating_navigator or item.column() != 0:
            return

        dataset_id = item.data(Qt.ItemDataRole.UserRole)

        if not isinstance(dataset_id, str):
            return

        package = self._workspace_state.workbook_package

        if package is None:
            return

        dataset = package.get_dataset(dataset_id)

        if dataset is None:
            return

        selected = item.checkState() == Qt.CheckState.Checked

        dataset.selected = selected
        dataset.status = PreparationStatus.NOT_REVIEWED if selected else PreparationStatus.EXCLUDED

        self._workspace_state.workbook_package_changed.emit()

    def _navigator_selection_changed(self) -> None:
        selected_rows = self._navigator_table.selectionModel().selectedRows()

        if not selected_rows:
            return

        row_number = selected_rows[0].row()
        item = self._navigator_table.item(
            row_number,
            1,
        )

        if item is None:
            return

        dataset_id = item.data(Qt.ItemDataRole.UserRole)

        if not isinstance(dataset_id, str):
            return

        try:
            self._workspace_state.set_active_dataset(dataset_id)
        except ValueError as error:
            self._set_navigator_status(
                str(error),
                "error",
            )

    def _dataset_name_changed(self) -> None:
        editor = self.sender()

        if not isinstance(editor, QLineEdit):
            return

        dataset_id = editor.property("dataset_id")

        if not isinstance(dataset_id, str):
            return

        package = self._workspace_state.workbook_package

        if package is None:
            return

        dataset = package.get_dataset(dataset_id)

        if dataset is None:
            return

        confirmed_name = editor.text().strip()

        if not confirmed_name:
            editor.setText(dataset.confirmed_display_name)
            self._set_navigator_status(
                "A dataset name cannot be blank.",
                "error",
            )
            return

        dataset.confirmed_display_name = confirmed_name

        if dataset.selected:
            dataset.status = PreparationStatus.NOT_REVIEWED

        self._set_navigator_status(
            (f"Dataset name updated to '{dataset.confirmed_display_name}'."),
            "success",
        )

    def _dataset_type_changed(self) -> None:
        combo = self.sender()

        if not isinstance(combo, QComboBox):
            return

        dataset_id = combo.property("dataset_id")
        selected_type = combo.currentData()

        if not isinstance(dataset_id, str) or not isinstance(
            selected_type,
            DatasetType,
        ):
            return

        package = self._workspace_state.workbook_package

        if package is None:
            return

        dataset = package.get_dataset(dataset_id)

        if dataset is None:
            return

        dataset.confirmed_dataset_type = selected_type

        if dataset.selected:
            dataset.status = PreparationStatus.NOT_REVIEWED

        dataset_type_label = self._suggestion_service.dataset_type_label(selected_type)

        self._set_navigator_status(
            (f"'{dataset.confirmed_display_name}' classified as {dataset_type_label}."),
            "success",
        )

    def _include_all_datasets(self) -> None:
        self._set_all_dataset_selection(True)

    def _exclude_all_datasets(self) -> None:
        self._set_all_dataset_selection(False)

    def _set_all_dataset_selection(
        self,
        selected: bool,
    ) -> None:
        package = self._workspace_state.workbook_package

        if package is None:
            return

        self._updating_navigator = True

        try:
            for dataset in package.datasets:
                dataset.selected = selected
                dataset.status = (
                    PreparationStatus.NOT_REVIEWED if selected else PreparationStatus.EXCLUDED
                )
        finally:
            self._updating_navigator = False

        self._workspace_state.workbook_package_changed.emit()

        action = "included" if selected else "excluded"

        self._set_navigator_status(
            f"All loaded datasets were {action}.",
            "success",
        )

    def _confirm_and_continue(self) -> None:
        package = self._workspace_state.workbook_package

        if package is None:
            self._set_navigator_status(
                ("Load data before continuing."),
                "error",
            )
            return

        selected_datasets = package.selected_datasets

        if not selected_datasets:
            self._set_navigator_status(
                ("Include at least one dataset before continuing."),
                "error",
            )
            return

        unnamed_datasets = [
            dataset.original_worksheet_name
            for dataset in selected_datasets
            if not dataset.confirmed_display_name.strip()
        ]

        if unnamed_datasets:
            self._set_navigator_status(
                (
                    "Every included dataset must have a "
                    "name. Review: "
                    f"{', '.join(unnamed_datasets)}."
                ),
                "error",
            )
            return

        unclassified_datasets = [
            dataset.confirmed_display_name
            for dataset in selected_datasets
            if (dataset.confirmed_dataset_type == DatasetType.UNCLASSIFIED)
        ]

        if unclassified_datasets:
            self._set_navigator_status(
                (
                    "Every included dataset must have a "
                    "confirmed dataset type. Select a type "
                    "or choose Other for: "
                    f"{', '.join(unclassified_datasets)}."
                ),
                "error",
            )
            return

        for dataset in package.datasets:
            dataset.status = (
                PreparationStatus.CONFIRMED if dataset.selected else PreparationStatus.EXCLUDED
            )

        first_dataset = selected_datasets[0]

        self._workspace_state.set_active_dataset(first_dataset.dataset_id)
        self._workspace_state.workbook_package_changed.emit()

        self._set_navigator_status(
            f"{self._dataset_count_text(len(selected_datasets))} selected.",
            "success",
        )

        self.continue_requested.emit("workspace.data_profile")

    def _select_active_dataset_row(self) -> None:
        active_dataset_id = self._workspace_state.active_dataset_id

        if active_dataset_id is None:
            return

        for row_number in range(self._navigator_table.rowCount()):
            item = self._navigator_table.item(
                row_number,
                1,
            )

            if item is None:
                continue

            if item.data(Qt.ItemDataRole.UserRole) == active_dataset_id:
                self._navigator_table.selectRow(row_number)
                return

    def _display_source_metadata(
        self,
        source_info: SourceFileInfo,
    ) -> None:
        self._path_field.setText(source_info.path.name)
        self._path_field.setToolTip(str(source_info.path))
        self._file_type_value.setText(source_info.file_type.upper())
        self._file_size_value.setText(self._format_file_size(source_info.file_size_bytes))
        self._worksheet_count_value.setText(f"{len(source_info.worksheets):,}")
        self._loaded_dataset_count_value.setText("0")

    def _clear_workspace(self) -> None:
        """Delegate audit clearing to the window's guarded transition flow."""

        self.clear_requested.emit()

    def _reset_page(self) -> None:
        self._source_path = None

        self._path_field.clear()
        self._path_field.setToolTip("")
        self._file_type_value.setText("—")
        self._file_size_value.setText("—")
        self._worksheet_count_value.setText("—")
        self._loaded_dataset_count_value.setText("—")

        self._navigator_table.clearContents()
        self._navigator_table.setRowCount(0)

        self._set_load_button_mode(reload=False)
        self._load_package_button.setEnabled(False)
        self._select_all_button.setEnabled(False)
        self._exclude_all_button.setEnabled(False)
        self._confirm_button.setEnabled(False)
        self._clear_button.setEnabled(False)

        self._set_source_status(
            "Select a source file to begin.",
            "neutral",
        )
        self._set_navigator_status(
            ("Select a source file to view its worksheets."),
            "neutral",
        )

    def _restore_state(self) -> None:
        source_info = self._workspace_state.source_info

        if source_info is None:
            return

        self._source_path = source_info.path
        self._display_source_metadata(source_info)

        self._clear_button.setEnabled(True)
        self._load_package_button.setEnabled(True)

        package = self._workspace_state.workbook_package

        if package is None:
            self._display_inspected_worksheets(source_info)
            self._set_source_status(
                "File selected and ready to load.",
                "success",
            )
            return

        self._set_load_button_mode(reload=True)
        self._refresh_loaded_package()

        self._set_source_status("", "neutral")
        self._set_navigator_status(
            f"{self._dataset_count_text(len(package.datasets))} available in the current audit.",
            "neutral",
        )

    def _set_source_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._source_status.setText(message)
        self._source_status.setVisible(bool(message))
        self._source_status.setProperty(
            "status",
            status,
        )
        self._refresh_status_style(self._source_status)

    def _set_navigator_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._navigator_status.setText(message)
        self._navigator_status.setProperty(
            "status",
            status,
        )
        self._refresh_status_style(self._navigator_status)

    def _set_load_button_mode(self, *, reload: bool) -> None:
        self._load_package_button.setText("Reload Data" if reload else "Load Data")
        self._load_package_button.setObjectName(
            "secondaryActionButton" if reload else "primaryActionButton"
        )
        self._load_package_button.style().unpolish(self._load_package_button)
        self._load_package_button.style().polish(self._load_package_button)

    @staticmethod
    def _dataset_count_text(count: int) -> str:
        noun = "dataset" if count == 1 else "datasets"
        return f"{count:,} {noun}"

    @staticmethod
    def _metadata_value() -> QLabel:
        label = QLabel("—")
        label.setObjectName("fieldHint")
        return label

    @staticmethod
    def _centred_item(
        value: str,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    @staticmethod
    def _status_label(
        status: PreparationStatus,
    ) -> str:
        labels = {
            PreparationStatus.NOT_REVIEWED: ("Review Required"),
            PreparationStatus.CONFIRMED: "Confirmed",
            PreparationStatus.CONFIRMED_WITH_WARNINGS: ("Confirmed with Warnings"),
            PreparationStatus.REVIEW_REQUIRED: ("Review Required"),
            PreparationStatus.EXCLUDED: "Excluded",
        }

        return labels[status]

    @staticmethod
    def _refresh_status_style(
        label: QLabel,
    ) -> None:
        label.style().unpolish(label)
        label.style().polish(label)

    @staticmethod
    def _format_file_size(
        size_bytes: int,
    ) -> str:
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
