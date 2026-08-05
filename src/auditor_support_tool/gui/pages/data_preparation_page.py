"""Page for preparing dataset columns before field mapping."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
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

from auditor_support_tool.core.data_preparation_service import (
    DataPreparationError,
    DataPreparationService,
)
from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
    PreparedColumn,
    WorksheetDataset,
)
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DetectedDataType,
)


class DataPreparationPage(QWidget):
    """Prepare confirmed worksheet datasets for field mapping."""

    back_requested = Signal(str)
    continue_requested = Signal(str)

    _CONFIRMED_STATUSES = {
        PreparationStatus.CONFIRMED,
        PreparationStatus.CONFIRMED_WITH_WARNINGS,
    }

    def __init__(
        self,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._preparation_service = DataPreparationService()

        self._updating_dataset_selector = False
        self._updating_columns_table = False

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

        navigation_layout = QHBoxLayout()
        navigation_layout.setSpacing(10)

        self._back_button = QPushButton("Back to Data Profile")
        self._back_button.setObjectName("secondaryActionButton")

        navigation_layout.addWidget(self._back_button)
        navigation_layout.addStretch(1)

        title = QLabel("Data Preparation")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Confirm column names, data types and included columns "
            "before mapping the data to standard audit fields."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addLayout(navigation_layout)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_dataset_card())
        layout.addWidget(self._build_columns_card())
        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_dataset_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Dataset")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Select a dataset confirmed in Data Sources. Preparation "
            "decisions are stored separately for each dataset."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        dataset_label = QLabel("Dataset being prepared")
        dataset_label.setObjectName("fieldLabel")

        self._dataset_selector = QComboBox()
        self._dataset_selector.setEnabled(False)

        self._dataset_summary = QLabel("No confirmed dataset is available.")
        self._dataset_summary.setObjectName("fieldHint")
        self._dataset_summary.setWordWrap(True)

        status_heading = QLabel("Dataset preparation status")
        status_heading.setObjectName("fieldLabel")

        self._dataset_status_container = QFrame()
        self._dataset_status_container.setObjectName("datasetPreparationStatusContainer")
        self._dataset_status_layout = QVBoxLayout(self._dataset_status_container)
        self._dataset_status_layout.setContentsMargins(0, 0, 0, 0)
        self._dataset_status_layout.setSpacing(6)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(dataset_label)
        layout.addWidget(self._dataset_selector)
        layout.addWidget(self._dataset_summary)
        layout.addWidget(status_heading)
        layout.addWidget(self._dataset_status_container)

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

        heading = QLabel("Column Preparation")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "The source column remains unchanged. Prepared names and "
            "confirmed data types define how the data will be interpreted "
            "during field mapping and audit testing."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._active_dataset_heading = QLabel("Preparing dataset: No dataset selected")
        self._active_dataset_heading.setObjectName("profileSectionTitle")
        self._active_dataset_heading.setWordWrap(True)

        self._columns_table = QTableWidget()
        self._columns_table.setColumnCount(8)
        self._columns_table.setHorizontalHeaderLabels(
            (
                "Include",
                "Source Column",
                "Prepared Name",
                "Detected Type",
                "Confirmed Type",
                "Changed",
                "Warning",
                "Status",
            )
        )
        self._columns_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._columns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._columns_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._columns_table.setAlternatingRowColors(True)
        self._columns_table.verticalHeader().setVisible(False)
        self._columns_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._columns_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header = self._columns_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.Stretch,
        )

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self._include_all_button = QPushButton("Include All Columns")
        self._include_all_button.setObjectName("secondaryActionButton")
        self._include_all_button.setEnabled(False)

        self._exclude_all_button = QPushButton("Exclude All Columns")
        self._exclude_all_button.setObjectName("secondaryActionButton")
        self._exclude_all_button.setEnabled(False)

        self._reset_button = QPushButton("Reset Dataset")
        self._reset_button.setObjectName("secondaryActionButton")
        self._reset_button.setEnabled(False)

        self._confirm_dataset_button = QPushButton("Confirm Dataset Preparation")
        self._confirm_dataset_button.setObjectName("primaryActionButton")
        self._confirm_dataset_button.setEnabled(False)

        self._continue_button = QPushButton("Continue to Field Mapping")
        self._continue_button.setObjectName("primaryActionButton")
        self._continue_button.setVisible(False)
        self._continue_button.setEnabled(False)

        actions_layout.addWidget(self._include_all_button)
        actions_layout.addWidget(self._exclude_all_button)
        actions_layout.addWidget(self._reset_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._confirm_dataset_button)
        actions_layout.addWidget(self._continue_button)

        self._preparation_status = QLabel("Select a dataset to begin preparation.")
        self._preparation_status.setObjectName("formStatus")
        self._preparation_status.setProperty("status", "neutral")
        self._preparation_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._active_dataset_heading)
        layout.addWidget(self._columns_table)
        layout.addLayout(actions_layout)
        layout.addWidget(self._preparation_status)

        return card

    def _connect_signals(self) -> None:
        self._dataset_selector.currentIndexChanged.connect(self._dataset_selection_changed)
        self._back_button.clicked.connect(
            lambda: self.back_requested.emit("workspace.data_profile")
        )

        self._columns_table.itemChanged.connect(self._column_include_changed)

        self._include_all_button.clicked.connect(lambda: self._set_all_columns_included(True))
        self._exclude_all_button.clicked.connect(lambda: self._set_all_columns_included(False))
        self._reset_button.clicked.connect(self._reset_active_dataset)
        self._confirm_dataset_button.clicked.connect(self._confirm_active_dataset)
        self._continue_button.clicked.connect(self._continue_to_field_mapping)

        self._workspace_state.workbook_package_changed.connect(self._refresh_page)
        self._workspace_state.active_dataset_changed.connect(self._refresh_page)
        self._workspace_state.workspace_cleared.connect(self._refresh_page)

    def _refresh_page(self) -> None:
        self._refresh_dataset_selector()
        self._refresh_dataset_status_list()

        dataset = self._active_preparation_dataset()

        if dataset is None:
            self._columns_table.clearContents()
            self._columns_table.setRowCount(0)
            self._adjust_columns_table_height()

            self._dataset_summary.setText("No confirmed dataset is available.")
            self._active_dataset_heading.setText("Preparing dataset: No dataset selected")
            self._set_preparation_status(
                "Select a confirmed dataset to begin.",
                "neutral",
            )
            self._set_action_buttons_enabled(False)
            self._continue_button.setVisible(False)
            self._continue_button.setEnabled(False)
            return

        self._display_dataset(dataset)
        self._populate_columns_table(dataset)
        self._set_action_buttons_enabled(True)
        self._update_confirm_button(dataset)
        self._update_continue_button()

    def _refresh_dataset_selector(self) -> None:
        confirmed_datasets = tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.status == PreparationStatus.CONFIRMED
        )

        active_dataset_id = self._workspace_state.active_dataset_id

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

    def _refresh_dataset_status_list(self) -> None:
        while self._dataset_status_layout.count():
            item = self._dataset_status_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        datasets = self._confirmed_source_datasets()

        if not datasets:
            empty_label = QLabel("No datasets have been confirmed in Data Sources.")
            empty_label.setObjectName("fieldHint")
            empty_label.setWordWrap(True)
            self._dataset_status_layout.addWidget(empty_label)
            return

        for dataset in datasets:
            row = QFrame()
            row.setObjectName("datasetPreparationStatusRow")

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)

            name_label = QLabel(dataset.confirmed_display_name)
            name_label.setObjectName("fieldHint")
            name_label.setWordWrap(True)

            status_label = QLabel(self._status_label(dataset.preparation_status))
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setMinimumWidth(180)
            status_label.setStyleSheet(self._status_badge_style(dataset.preparation_status))

            row_layout.addWidget(name_label, 1)
            row_layout.addWidget(status_label)

            self._dataset_status_layout.addWidget(row)

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
            self._set_preparation_status(
                str(error),
                "error",
            )

    def _display_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        dataset_type = dataset.confirmed_dataset_type.value.replace("_", " ").title()

        self._dataset_summary.setText(
            f"Worksheet: {dataset.original_worksheet_name} | "
            f"Type: {dataset_type} | "
            f"Records: {dataset.record_count:,} | "
            f"Columns: {dataset.column_count:,}"
        )
        self._active_dataset_heading.setText(f"Preparing dataset: {dataset.confirmed_display_name}")

    def _populate_columns_table(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        self._updating_columns_table = True

        try:
            self._columns_table.clearContents()
            self._columns_table.setRowCount(len(dataset.columns))

            for row_number, column in enumerate(dataset.columns):
                self._populate_column_row(
                    row_number,
                    dataset,
                    column,
                )

            self._columns_table.resizeRowsToContents()
        finally:
            self._updating_columns_table = False

        self._adjust_columns_table_height()

    def _adjust_columns_table_height(self) -> None:
        header_height = self._columns_table.horizontalHeader().height()
        frame_height = self._columns_table.frameWidth() * 2

        rows_height = sum(
            self._columns_table.rowHeight(row) for row in range(self._columns_table.rowCount())
        )

        if self._columns_table.rowCount() == 0:
            rows_height = self._columns_table.verticalHeader().defaultSectionSize()

        target_height = header_height + rows_height + frame_height + 4
        maximum_height = 520
        minimum_height = (
            header_height
            + self._columns_table.verticalHeader().defaultSectionSize()
            + frame_height
            + 4
        )

        self._columns_table.setFixedHeight(
            max(
                minimum_height,
                min(target_height, maximum_height),
            )
        )

    def _populate_column_row(
        self,
        row_number: int,
        dataset: WorksheetDataset,
        column: PreparedColumn,
    ) -> None:
        include_item = QTableWidgetItem()
        include_item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        include_item.setCheckState(
            Qt.CheckState.Checked if column.included else Qt.CheckState.Unchecked
        )
        include_item.setData(
            Qt.ItemDataRole.UserRole,
            column.source_column,
        )

        source_item = QTableWidgetItem(column.source_column)

        name_editor = QLineEdit(column.confirmed_name)
        name_editor.setProperty(
            "source_column",
            column.source_column,
        )
        name_editor.setProperty(
            "dataset_id",
            dataset.dataset_id,
        )
        name_editor.editingFinished.connect(self._prepared_name_changed)

        detected_item = self._centred_item(self._type_label(column.detected_type))

        type_combo = QComboBox()
        type_combo.setProperty(
            "source_column",
            column.source_column,
        )
        type_combo.setProperty(
            "dataset_id",
            dataset.dataset_id,
        )

        for data_type in DetectedDataType:
            type_combo.addItem(
                self._type_label(data_type),
                data_type,
            )

        type_index = type_combo.findData(column.confirmed_type)

        if type_index >= 0:
            type_combo.setCurrentIndex(type_index)

        type_combo.currentIndexChanged.connect(self._confirmed_type_changed)

        changed_item = self._centred_item("Yes" if column.was_changed else "No")
        warning_item = QTableWidgetItem(column.validation_warning or "—")
        status_item = self._centred_item(self._status_label(column.status))

        self._columns_table.setItem(
            row_number,
            0,
            include_item,
        )
        self._columns_table.setItem(
            row_number,
            1,
            source_item,
        )
        self._columns_table.setCellWidget(
            row_number,
            2,
            name_editor,
        )
        self._columns_table.setItem(
            row_number,
            3,
            detected_item,
        )
        self._columns_table.setCellWidget(
            row_number,
            4,
            type_combo,
        )
        self._columns_table.setItem(
            row_number,
            5,
            changed_item,
        )
        self._columns_table.setItem(
            row_number,
            6,
            warning_item,
        )
        self._columns_table.setItem(
            row_number,
            7,
            status_item,
        )

    def _column_include_changed(
        self,
        item: QTableWidgetItem,
    ) -> None:
        if self._updating_columns_table or item.column() != 0:
            return

        dataset = self._active_preparation_dataset()

        if dataset is None:
            return

        source_column = item.data(Qt.ItemDataRole.UserRole)

        if not isinstance(source_column, str):
            return

        included = item.checkState() == Qt.CheckState.Checked

        try:
            self._preparation_service.set_column_included(
                dataset,
                source_column,
                included,
            )
        except DataPreparationError as error:
            self._set_preparation_status(
                str(error),
                "error",
            )
            return

        self._refresh_page()

    def _prepared_name_changed(self) -> None:
        editor = self.sender()

        if not isinstance(editor, QLineEdit):
            return

        dataset = self._dataset_from_widget(editor)

        if dataset is None:
            return

        source_column = editor.property("source_column")

        if not isinstance(source_column, str):
            return

        try:
            self._preparation_service.update_column_name(
                dataset,
                source_column,
                editor.text(),
            )
        except DataPreparationError as error:
            column = self._find_column(
                dataset,
                source_column,
            )

            if column is not None:
                editor.blockSignals(True)
                editor.setText(column.confirmed_name)
                editor.blockSignals(False)

            editor.setToolTip(str(error))
            editor.setFocus()
            editor.selectAll()

            self._set_preparation_status(
                (f"{error} The previous valid prepared name has been restored."),
                "error",
            )
            return

        editor.setToolTip("")

        self._set_preparation_status(
            f"Prepared name updated for '{source_column}'.",
            "success",
        )
        self._refresh_page()

    def _confirmed_type_changed(self) -> None:
        combo = self.sender()

        if not isinstance(combo, QComboBox):
            return

        dataset = self._dataset_from_widget(combo)

        if dataset is None:
            return

        source_column = combo.property("source_column")
        confirmed_type = combo.currentData()

        if not isinstance(source_column, str) or not isinstance(
            confirmed_type,
            DetectedDataType,
        ):
            return

        try:
            column = self._preparation_service.update_column_type(
                dataset,
                source_column,
                confirmed_type,
            )
        except DataPreparationError as error:
            self._set_preparation_status(
                str(error),
                "error",
            )
            return

        if column.validation_warning:
            self._set_preparation_status(
                column.validation_warning,
                "neutral",
            )
        else:
            self._set_preparation_status(
                (f"Confirmed type updated for '{source_column}'."),
                "success",
            )

        self._refresh_page()

    def _set_all_columns_included(
        self,
        included: bool,
    ) -> None:
        dataset = self._active_preparation_dataset()

        if dataset is None:
            return

        for column in dataset.columns:
            self._preparation_service.set_column_included(
                dataset,
                column.source_column,
                included,
            )

        action = "included" if included else "excluded"

        self._set_preparation_status(
            f"All columns were {action}.",
            "success",
        )
        self._refresh_page()

    def _reset_active_dataset(self) -> None:
        dataset = self._active_preparation_dataset()

        if dataset is None:
            return

        self._preparation_service.reset_dataset(dataset)

        self._set_preparation_status(
            (
                f"Preparation for "
                f"'{dataset.confirmed_display_name}' "
                "was reset to the detected suggestions."
            ),
            "success",
        )
        self._refresh_page()

    def _confirm_active_dataset(self) -> None:
        dataset = self._active_preparation_dataset()

        if dataset is None:
            self._set_preparation_status(
                "Select a dataset before confirming preparation.",
                "error",
            )
            return

        try:
            status = self._preparation_service.confirm_dataset(dataset)
        except DataPreparationError as error:
            self._set_preparation_status(
                str(error),
                "error",
            )
            return

        if status == PreparationStatus.CONFIRMED_WITH_WARNINGS:
            confirmation_message = (
                f"'{dataset.confirmed_display_name}' was confirmed with data-type warnings."
            )
            confirmation_style = "neutral"
        else:
            confirmation_message = f"'{dataset.confirmed_display_name}' preparation was confirmed."
            confirmation_style = "success"

        next_dataset = self._next_unreviewed_dataset(current_dataset_id=dataset.dataset_id)

        if next_dataset is not None:
            self._set_preparation_status(
                (f"{confirmation_message} Moving to '{next_dataset.confirmed_display_name}'."),
                confirmation_style,
            )
            self._workspace_state.set_active_dataset(next_dataset.dataset_id)
            return

        self._set_preparation_status(
            confirmation_message,
            confirmation_style,
        )
        self._refresh_page()

    def _next_unreviewed_dataset(
        self,
        current_dataset_id: str,
    ) -> WorksheetDataset | None:
        """Return the next dataset that still needs preparation."""

        datasets = self._confirmed_source_datasets()

        if not datasets:
            return None

        current_index = next(
            (
                index
                for index, dataset in enumerate(datasets)
                if dataset.dataset_id == current_dataset_id
            ),
            -1,
        )

        ordered_candidates = datasets[current_index + 1 :] + datasets[: current_index + 1]

        return next(
            (
                dataset
                for dataset in ordered_candidates
                if dataset.preparation_status not in self._CONFIRMED_STATUSES
            ),
            None,
        )

    def _continue_to_field_mapping(self) -> None:
        incomplete_datasets = tuple(
            dataset.confirmed_display_name
            for dataset in self._workspace_state.selected_datasets
            if dataset.preparation_status
            not in {
                PreparationStatus.CONFIRMED,
                PreparationStatus.CONFIRMED_WITH_WARNINGS,
            }
        )

        if incomplete_datasets:
            self._set_preparation_status(
                (
                    "Confirm preparation for every included "
                    "dataset before continuing. Review: "
                    f"{', '.join(incomplete_datasets)}."
                ),
                "error",
            )
            return

        self.continue_requested.emit("workspace.field_mapping")

    def _update_continue_button(self) -> None:
        all_confirmed = self._all_datasets_confirmed()
        self._continue_button.setVisible(all_confirmed)
        self._continue_button.setEnabled(all_confirmed)

    def _update_confirm_button(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        status = dataset.preparation_status

        if status == PreparationStatus.CONFIRMED:
            background = "#198754"
            hover = "#157347"
            text = "Confirmed"
        elif status == PreparationStatus.CONFIRMED_WITH_WARNINGS:
            background = "#d18b00"
            hover = "#b97800"
            text = "Confirmed with Warnings"
        else:
            background = "#c62828"
            hover = "#a91f1f"
            text = "Confirm Dataset Preparation"

        self._confirm_dataset_button.setText(text)
        self._confirm_dataset_button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {background};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:disabled {{
                background-color: #777777;
                color: #dddddd;
            }}
            """
        )

    def _all_datasets_confirmed(self) -> bool:
        datasets = self._confirmed_source_datasets()

        return bool(datasets) and all(
            dataset.preparation_status in self._CONFIRMED_STATUSES for dataset in datasets
        )

    def _confirmed_source_datasets(
        self,
    ) -> tuple[WorksheetDataset, ...]:
        return tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.status == PreparationStatus.CONFIRMED
        )

    def _active_preparation_dataset(
        self,
    ) -> WorksheetDataset | None:
        dataset = self._workspace_state.active_dataset

        if dataset is None or not dataset.selected or dataset.status != PreparationStatus.CONFIRMED:
            return None

        return dataset

    def _dataset_from_widget(
        self,
        widget: QWidget,
    ) -> WorksheetDataset | None:
        dataset_id = widget.property("dataset_id")

        if not isinstance(dataset_id, str):
            return None

        package = self._workspace_state.workbook_package

        if package is None:
            return None

        return package.get_dataset(dataset_id)

    @staticmethod
    def _find_column(
        dataset: WorksheetDataset,
        source_column: str,
    ) -> PreparedColumn | None:
        return next(
            (column for column in dataset.columns if column.source_column == source_column),
            None,
        )

    def _set_action_buttons_enabled(
        self,
        enabled: bool,
    ) -> None:
        self._include_all_button.setEnabled(enabled)
        self._exclude_all_button.setEnabled(enabled)
        self._reset_button.setEnabled(enabled)
        self._confirm_dataset_button.setEnabled(enabled)

    def _set_preparation_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._preparation_status.setText(message)
        self._preparation_status.setProperty(
            "status",
            status,
        )
        self._refresh_status_style(self._preparation_status)

    @staticmethod
    def _status_badge_style(
        status: PreparationStatus,
    ) -> str:
        if status == PreparationStatus.CONFIRMED:
            background = "#198754"
        elif status == PreparationStatus.CONFIRMED_WITH_WARNINGS:
            background = "#d18b00"
        else:
            background = "#c62828"

        return (
            f"background-color: {background};"
            "color: white;"
            "border-radius: 5px;"
            "padding: 5px 10px;"
            "font-weight: 600;"
        )

    @staticmethod
    def _centred_item(
        value: str,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    @staticmethod
    def _type_label(
        data_type: DetectedDataType,
    ) -> str:
        return data_type.value.replace(
            "_",
            " ",
        ).title()

    @staticmethod
    def _status_label(
        status: PreparationStatus,
    ) -> str:
        labels = {
            PreparationStatus.NOT_REVIEWED: "Review Required",
            PreparationStatus.CONFIRMED: "Confirmed",
            PreparationStatus.CONFIRMED_WITH_WARNINGS: ("Confirmed with Warnings"),
            PreparationStatus.REVIEW_REQUIRED: "Review Required",
            PreparationStatus.EXCLUDED: "Excluded",
        }

        return labels[status]

    @staticmethod
    def _refresh_status_style(
        label: QLabel,
    ) -> None:
        label.style().unpolish(label)
        label.style().polish(label)
