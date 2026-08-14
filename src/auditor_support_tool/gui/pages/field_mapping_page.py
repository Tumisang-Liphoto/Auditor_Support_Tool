"""Page for mapping prepared columns to standard audit fields."""

import re
from difflib import SequenceMatcher

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
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

from auditor_support_tool.core.field_mapping_models import (
    StandardAuditField,
)
from auditor_support_tool.core.field_mapping_service import (
    FieldMappingError,
    FieldMappingService,
)
from auditor_support_tool.core.workbook_package import (
    FieldMappingStatus,
    PreparationStatus,
    PreparedColumn,
    WorksheetDataset,
)
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse-wheel selection changes."""

    def wheelEvent(self, event) -> None:
        event.ignore()


class FieldMappingPage(QWidget):
    """Map prepared dataset columns to standard audit fields."""

    back_requested = Signal(str)
    continue_requested = Signal(str)

    _FINAL_MAPPING_STATUSES = {
        FieldMappingStatus.CONFIRMED,
        FieldMappingStatus.CONFIRMED_WITH_WARNINGS,
        FieldMappingStatus.NOT_APPLICABLE,
    }

    def __init__(
        self,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._mapping_service = FieldMappingService()

        self._updating_dataset_selector = False
        self._updating_mapping_table = False

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

        self._back_button = QPushButton("Back to Data Preparation")
        self._back_button.setObjectName("secondaryActionButton")

        navigation_layout.addWidget(self._back_button)
        navigation_layout.addStretch(1)

        title = QLabel("Field Mapping")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Map prepared auditee-specific columns to standard "
            "audit fields used by later audit procedures."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addLayout(navigation_layout)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_dataset_card())
        layout.addWidget(self._build_mapping_card())
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
            "Only datasets confirmed in Data Preparation are available for field mapping."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        dataset_label = QLabel("Dataset being mapped")
        dataset_label.setObjectName("fieldLabel")

        self._dataset_selector = QComboBox()
        self._dataset_selector.setEnabled(False)

        self._dataset_summary = QLabel("No prepared dataset is available.")
        self._dataset_summary.setObjectName("fieldHint")
        self._dataset_summary.setWordWrap(True)

        status_heading = QLabel("Dataset mapping status")
        status_heading.setObjectName("fieldLabel")

        self._dataset_status_container = QFrame()
        self._dataset_status_container.setObjectName("datasetMappingStatusContainer")
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

    def _build_mapping_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        heading = QLabel("Source-to-Standard Field Mapping")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Each standard field may only be mapped once within "
            "a dataset. Review the suggested mappings and change "
            "them where necessary before confirming the dataset."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._active_dataset_heading = QLabel("Mapping dataset: No dataset selected")
        self._active_dataset_heading.setObjectName("profileSectionTitle")
        self._active_dataset_heading.setWordWrap(True)

        self._mapping_table = QTableWidget()
        self._mapping_table.setColumnCount(5)
        self._mapping_table.setHorizontalHeaderLabels(
            (
                "Prepared Name",
                "Prepared Type",
                "Standard Audit Field",
                "Description",
                "Mapping Status",
            )
        )
        self._mapping_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._mapping_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._mapping_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._mapping_table.setAlternatingRowColors(True)
        self._mapping_table.verticalHeader().setVisible(False)
        self._mapping_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mapping_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        header = self._mapping_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self._reset_button = QPushButton("Reset Dataset Mapping")
        self._reset_button.setObjectName("secondaryActionButton")
        self._reset_button.setEnabled(False)

        self._confirm_button = QPushButton("Confirm Dataset Mapping")
        self._confirm_button.setObjectName("primaryActionButton")
        self._confirm_button.setEnabled(False)

        self._continue_button = QPushButton("Continue to Audit Procedures")
        self._continue_button.setObjectName("primaryActionButton")
        self._continue_button.setVisible(False)
        self._continue_button.setEnabled(False)

        actions_layout.addWidget(self._reset_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self._confirm_button)
        actions_layout.addWidget(self._continue_button)

        self._mapping_status = QLabel("Select a prepared dataset to begin mapping.")
        self._mapping_status.setObjectName("formStatus")
        self._mapping_status.setProperty(
            "status",
            "neutral",
        )
        self._mapping_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._active_dataset_heading)
        layout.addWidget(self._mapping_table)
        layout.addLayout(actions_layout)
        layout.addWidget(self._mapping_status)

        return card

    def _connect_signals(self) -> None:
        self._dataset_selector.currentIndexChanged.connect(self._dataset_selection_changed)
        self._back_button.clicked.connect(
            lambda: self.back_requested.emit("workspace.data_preparation")
        )

        self._reset_button.clicked.connect(self._reset_active_dataset)
        self._confirm_button.clicked.connect(self._confirm_active_dataset)
        self._continue_button.clicked.connect(self._continue_to_audit_procedures)

        self._workspace_state.workbook_package_changed.connect(self._refresh_page)
        self._workspace_state.active_dataset_changed.connect(self._refresh_page)
        self._workspace_state.workspace_cleared.connect(self._refresh_page)

    def _refresh_page(self) -> None:
        self._refresh_dataset_selector()
        self._refresh_dataset_status_list()

        dataset = self._active_mapping_dataset()

        if dataset is None:
            self._mapping_table.clearContents()
            self._mapping_table.setRowCount(0)
            self._adjust_mapping_table_height()

            self._dataset_summary.setText("No prepared dataset is available.")
            self._active_dataset_heading.setText("Mapping dataset: No dataset selected")
            self._set_mapping_status(
                "Select a prepared dataset to begin.",
                "neutral",
            )

            self._set_action_buttons_enabled(False)
            self._continue_button.setVisible(False)
            self._continue_button.setEnabled(False)
            return

        self._apply_mapping_suggestions(dataset)
        self._display_dataset(dataset)
        self._populate_mapping_table(dataset)
        self._set_action_buttons_enabled(True)
        self._update_confirm_button(dataset)
        self._update_continue_button()

    def _refresh_dataset_selector(self) -> None:
        prepared_datasets = tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.preparation_status
            in {
                PreparationStatus.CONFIRMED,
                PreparationStatus.CONFIRMED_WITH_WARNINGS,
            }
        )

        active_dataset_id = self._workspace_state.active_dataset_id

        self._updating_dataset_selector = True

        try:
            self._dataset_selector.clear()

            for dataset in prepared_datasets:
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

        datasets = self._prepared_datasets()

        if not datasets:
            empty_label = QLabel("No datasets have completed Data Preparation.")
            empty_label.setObjectName("fieldHint")
            empty_label.setWordWrap(True)
            self._dataset_status_layout.addWidget(empty_label)
            return

        for dataset in datasets:
            row = QFrame()
            row.setObjectName("datasetMappingStatusRow")

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(12)

            name_label = QLabel(dataset.confirmed_display_name)
            name_label.setObjectName("fieldHint")
            name_label.setWordWrap(True)

            status_label = QLabel(self._mapping_status_label(dataset.mapping_status))
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setMinimumWidth(180)
            status_label.setStyleSheet(self._mapping_status_badge_style(dataset.mapping_status))

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
            self._set_mapping_status(
                str(error),
                "error",
            )

    def _display_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        dataset_type = dataset.confirmed_dataset_type.value.replace("_", " ").title()

        self._dataset_summary.setText(
            f"Worksheet: "
            f"{dataset.original_worksheet_name} | "
            f"Type: {dataset_type} | "
            f"Included columns: "
            f"{len(dataset.included_columns):,}"
        )
        self._active_dataset_heading.setText(f"Mapping dataset: {dataset.confirmed_display_name}")

    def _populate_mapping_table(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        included_columns = dataset.included_columns
        catalogue = tuple(
            sorted(
                self._mapping_service.available_fields(dataset),
                key=lambda field: field.display_name.casefold(),
            )
        )

        self._updating_mapping_table = True

        try:
            self._mapping_table.clearContents()
            self._mapping_table.setRowCount(len(included_columns))

            for row_number, column in enumerate(included_columns):
                self._populate_mapping_row(
                    row_number,
                    dataset,
                    column,
                    catalogue,
                )

            self._mapping_table.resizeRowsToContents()
        finally:
            self._updating_mapping_table = False

        self._adjust_mapping_table_height()

    def _adjust_mapping_table_height(self) -> None:
        header_height = self._mapping_table.horizontalHeader().height()
        frame_height = self._mapping_table.frameWidth() * 2
        rows_height = sum(
            self._mapping_table.rowHeight(row) for row in range(self._mapping_table.rowCount())
        )

        if self._mapping_table.rowCount() == 0:
            rows_height = self._mapping_table.verticalHeader().defaultSectionSize()

        target_height = header_height + rows_height + frame_height + 4
        maximum_height = 520
        minimum_height = (
            header_height
            + self._mapping_table.verticalHeader().defaultSectionSize()
            + frame_height
            + 4
        )
        self._mapping_table.setFixedHeight(max(minimum_height, min(target_height, maximum_height)))

    def _apply_mapping_suggestions(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        catalogue = tuple(
            sorted(
                self._mapping_service.available_fields(dataset),
                key=lambda field: field.display_name.casefold(),
            )
        )

        if not catalogue:
            return

        used_keys = {field_key for field_key in dataset.field_mappings.values() if field_key}

        for column in dataset.included_columns:
            if dataset.field_mappings.get(column.column_id):
                continue

            candidates = tuple(field for field in catalogue if field.key not in used_keys)

            if not candidates:
                break

            suggested_field = max(
                candidates,
                key=lambda field: self._mapping_similarity(
                    column.confirmed_name,
                    field,
                ),
            )
            score = self._mapping_similarity(
                column.confirmed_name,
                suggested_field,
            )

            if score < 0.45:
                continue

            try:
                self._mapping_service.assign_mapping(
                    dataset,
                    column.column_id,
                    suggested_field.key,
                )
            except FieldMappingError:
                continue

            self._record_transformation(
                action="field_mapping_assigned",
                dataset=dataset,
                column=column,
                old_value=None,
                new_value=suggested_field.key,
                details={
                    "method": "automatic_suggestion",
                    "prepared_name": column.confirmed_name,
                },
            )

            used_keys.add(suggested_field.key)

    @classmethod
    def _mapping_similarity(
        cls,
        prepared_name: str,
        field: StandardAuditField,
    ) -> float:
        prepared = cls._normalise_mapping_text(prepared_name)
        display_name = cls._normalise_mapping_text(field.display_name)
        field_key = cls._normalise_mapping_text(field.key)

        if not prepared:
            return 0.0

        if prepared in {display_name, field_key}:
            return 1.0

        prepared_tokens = set(prepared.split())
        display_tokens = set(display_name.split())
        token_score = 0.0

        if prepared_tokens and display_tokens:
            token_score = len(prepared_tokens & display_tokens) / len(
                prepared_tokens | display_tokens
            )

        return max(
            SequenceMatcher(None, prepared, display_name).ratio(),
            SequenceMatcher(None, prepared, field_key).ratio(),
            token_score,
        )

    @staticmethod
    def _normalise_mapping_text(value: str) -> str:
        words = re.findall(r"[a-z0-9]+", value.casefold())
        return " ".join(words)

    def _populate_mapping_row(
        self,
        row_number: int,
        dataset: WorksheetDataset,
        column: PreparedColumn,
        catalogue: tuple[StandardAuditField, ...],
    ) -> None:
        prepared_name_item = QTableWidgetItem(column.confirmed_name)
        prepared_type_item = self._centred_item(
            column.confirmed_type.value.replace("_", " ").title()
        )

        mapping_combo = NoWheelComboBox()
        mapping_combo.setProperty(
            "dataset_id",
            dataset.dataset_id,
        )
        mapping_combo.setProperty(
            "column_id",
            column.column_id,
        )

        mapping_combo.addItem(
            "Not mapped",
            "",
        )

        mapped_key = dataset.field_mappings.get(
            column.column_id,
            "",
        )
        used_keys = {
            field_key
            for mapped_column_id, field_key in dataset.field_mappings.items()
            if mapped_column_id != column.column_id and field_key
        }

        for field in catalogue:
            if field.key in used_keys:
                continue

            label = field.display_name

            mapping_combo.addItem(
                label,
                field.key,
            )

        mapped_index = mapping_combo.findData(mapped_key)

        if mapped_index >= 0:
            mapping_combo.setCurrentIndex(mapped_index)

        mapping_combo.currentIndexChanged.connect(self._mapping_changed)

        mapped_field = self._mapping_service.mapped_field(
            dataset,
            column.column_id,
        )

        description_text = mapped_field.description if mapped_field is not None else "—"
        description_item = QTableWidgetItem(description_text)
        description_item.setToolTip(description_text)

        mapping_status_item = self._centred_item(
            "Mapped" if mapped_field is not None else "Not Mapped"
        )

        self._mapping_table.setItem(
            row_number,
            0,
            prepared_name_item,
        )
        self._mapping_table.setItem(
            row_number,
            1,
            prepared_type_item,
        )
        self._mapping_table.setCellWidget(
            row_number,
            2,
            mapping_combo,
        )
        self._mapping_table.setItem(
            row_number,
            3,
            description_item,
        )
        self._mapping_table.setItem(
            row_number,
            4,
            mapping_status_item,
        )

    def _mapping_changed(self) -> None:
        if self._updating_mapping_table:
            return

        combo = self.sender()

        if not isinstance(combo, QComboBox):
            return

        dataset = self._dataset_from_widget(combo)

        if dataset is None:
            return

        column_id = combo.property("column_id")
        standard_field_key = combo.currentData()

        if not isinstance(column_id, str) or not isinstance(
            standard_field_key,
            str,
        ):
            return

        column = dataset.get_column(column_id)

        if column is None:
            return

        previous_key = dataset.field_mappings.get(
            column_id,
            "",
        )

        try:
            self._mapping_service.assign_mapping(
                dataset,
                column_id,
                standard_field_key,
            )
        except FieldMappingError as error:
            combo.blockSignals(True)

            previous_index = combo.findData(previous_key)

            if previous_index >= 0:
                combo.setCurrentIndex(previous_index)

            combo.blockSignals(False)

            self._set_mapping_status(
                str(error),
                "error",
            )
            return

        if previous_key != standard_field_key:
            if previous_key and standard_field_key:
                action = "field_mapping_changed"
            elif standard_field_key:
                action = "field_mapping_assigned"
            else:
                action = "field_mapping_removed"

            self._record_transformation(
                action=action,
                dataset=dataset,
                column=column,
                old_value=previous_key or None,
                new_value=standard_field_key or None,
                details={"method": "manual"},
            )

        if standard_field_key:
            self._set_mapping_status(
                (f"Mapping updated for '{column.source_column}'."),
                "success",
            )
        else:
            self._set_mapping_status(
                (f"Mapping removed from '{column.source_column}'."),
                "success",
            )

        self._refresh_page()

    def _reset_active_dataset(self) -> None:
        dataset = self._active_mapping_dataset()

        if dataset is None:
            return

        previous_status = dataset.mapping_status
        previous_mapping_count = len(dataset.field_mappings)

        self._mapping_service.reset_dataset(dataset)

        self._record_transformation(
            action="field_mapping_reset",
            dataset=dataset,
            old_value=previous_status.value,
            new_value=dataset.mapping_status.value,
            details={
                "removed_mapping_count": previous_mapping_count,
            },
        )

        self._set_mapping_status(
            (f"Mappings for '{dataset.confirmed_display_name}' were reset."),
            "success",
        )
        self._refresh_page()

    def _confirm_active_dataset(self) -> None:
        dataset = self._active_mapping_dataset()

        if dataset is None:
            self._set_mapping_status(
                "Select a prepared dataset before confirming.",
                "error",
            )
            return

        previous_status = dataset.mapping_status

        try:
            status = self._mapping_service.confirm_dataset(dataset)
        except FieldMappingError as error:
            self._set_mapping_status(
                str(error),
                "error",
            )
            self._refresh_page()
            return

        self._record_transformation(
            action="field_mapping_confirmed",
            dataset=dataset,
            old_value=previous_status.value,
            new_value=status.value,
        )

        if status == FieldMappingStatus.NOT_APPLICABLE:
            confirmation_message = (
                "No standard-field catalogue is defined for "
                f"'{dataset.confirmed_display_name}'. Mapping "
                "was recorded as Not Applicable."
            )
            confirmation_style = "success"
        elif status == FieldMappingStatus.CONFIRMED_WITH_WARNINGS:
            confirmation_message = (
                f"Field mapping for '{dataset.confirmed_display_name}' was confirmed with warnings."
            )
            confirmation_style = "neutral"
        else:
            confirmation_message = (
                f"Field mapping for '{dataset.confirmed_display_name}' was confirmed."
            )
            confirmation_style = "success"

        next_dataset = self._next_unreviewed_dataset(current_dataset_id=dataset.dataset_id)

        if next_dataset is not None:
            self._set_mapping_status(
                (f"{confirmation_message} Moving to '{next_dataset.confirmed_display_name}'."),
                confirmation_style,
            )
            self._workspace_state.set_active_dataset(next_dataset.dataset_id)
            return

        self._set_mapping_status(
            confirmation_message,
            confirmation_style,
        )
        self._refresh_page()

    def _next_unreviewed_dataset(
        self,
        current_dataset_id: str,
    ) -> WorksheetDataset | None:
        """Return the next dataset whose mapping is not final."""

        datasets = self._prepared_datasets()

        if not datasets:
            return None

        current_index = next(
            (
                index
                for index, candidate in enumerate(datasets)
                if candidate.dataset_id == current_dataset_id
            ),
            -1,
        )

        ordered_candidates = datasets[current_index + 1 :] + datasets[: current_index + 1]

        return next(
            (
                candidate
                for candidate in ordered_candidates
                if candidate.mapping_status not in self._FINAL_MAPPING_STATUSES
            ),
            None,
        )

    def _continue_to_audit_procedures(self) -> None:
        incomplete_datasets = tuple(
            dataset.confirmed_display_name
            for dataset in self._prepared_datasets()
            if dataset.mapping_status
            not in {
                FieldMappingStatus.CONFIRMED,
                FieldMappingStatus.CONFIRMED_WITH_WARNINGS,
                FieldMappingStatus.NOT_APPLICABLE,
            }
        )

        if incomplete_datasets:
            self._set_mapping_status(
                (
                    "Confirm field mapping for every prepared "
                    "dataset before continuing. Review: "
                    f"{', '.join(incomplete_datasets)}."
                ),
                "error",
            )
            return

        if not self._prepared_datasets():
            self._set_mapping_status(
                ("No prepared dataset is available for field mapping."),
                "error",
            )
            return

        self.continue_requested.emit("workspace.audit_procedures")

    def _update_continue_button(self) -> None:
        all_confirmed = self._all_datasets_mapped()
        self._continue_button.setVisible(all_confirmed)
        self._continue_button.setEnabled(all_confirmed)

    def _update_confirm_button(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        status = dataset.mapping_status

        if status == FieldMappingStatus.CONFIRMED:
            background = "#198754"
            hover = "#157347"
            text = "Confirmed"
        elif status == FieldMappingStatus.CONFIRMED_WITH_WARNINGS:
            background = "#d18b00"
            hover = "#b97800"
            text = "Confirmed with Warnings"
        elif status == FieldMappingStatus.NOT_APPLICABLE:
            background = "#198754"
            hover = "#157347"
            text = "Not Applicable"
        else:
            background = "#c62828"
            hover = "#a91f1f"
            text = "Confirm Dataset Mapping"

        self._confirm_button.setText(text)
        self._confirm_button.setStyleSheet(
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

    def _all_datasets_mapped(self) -> bool:
        datasets = self._prepared_datasets()

        return bool(datasets) and all(
            dataset.mapping_status in self._FINAL_MAPPING_STATUSES for dataset in datasets
        )

    def _prepared_datasets(
        self,
    ) -> tuple[WorksheetDataset, ...]:
        return tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.preparation_status
            in {
                PreparationStatus.CONFIRMED,
                PreparationStatus.CONFIRMED_WITH_WARNINGS,
            }
        )

    def _active_mapping_dataset(
        self,
    ) -> WorksheetDataset | None:
        dataset = self._workspace_state.active_dataset

        if (
            dataset is None
            or not dataset.selected
            or dataset.preparation_status
            not in {
                PreparationStatus.CONFIRMED,
                PreparationStatus.CONFIRMED_WITH_WARNINGS,
            }
        ):
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

    def _record_transformation(
        self,
        *,
        action: str,
        dataset: WorksheetDataset,
        column: PreparedColumn | None = None,
        old_value: object | None = None,
        new_value: object | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        """Record a field-mapping change in workspace history."""

        if not self._workspace_state.has_workspace:
            return

        self._workspace_state.record_transformation(
            action=action,
            dataset_id=dataset.dataset_id,
            column_id=column.column_id if column is not None else None,
            source_column=column.source_column if column is not None else None,
            old_value=old_value,
            new_value=new_value,
            details=details,
        )

    def _set_action_buttons_enabled(
        self,
        enabled: bool,
    ) -> None:
        self._reset_button.setEnabled(enabled)
        self._confirm_button.setEnabled(enabled)

    def _set_mapping_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._mapping_status.setText(message)
        self._mapping_status.setProperty(
            "status",
            status,
        )
        self._refresh_status_style(self._mapping_status)

    @staticmethod
    def _mapping_status_badge_style(
        status: FieldMappingStatus,
    ) -> str:
        if status == FieldMappingStatus.CONFIRMED:
            background = "#198754"
        elif status == FieldMappingStatus.CONFIRMED_WITH_WARNINGS:
            background = "#d18b00"
        elif status == FieldMappingStatus.NOT_APPLICABLE:
            background = "#198754"
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
    def _mapping_status_label(
        status: FieldMappingStatus,
    ) -> str:
        labels = {
            FieldMappingStatus.NOT_STARTED: ("Not Started"),
            FieldMappingStatus.IN_PROGRESS: ("In Progress"),
            FieldMappingStatus.CONFIRMED: ("Confirmed"),
            FieldMappingStatus.CONFIRMED_WITH_WARNINGS: ("Confirmed with Warnings"),
            FieldMappingStatus.REVIEW_REQUIRED: ("Review Required"),
            FieldMappingStatus.NOT_APPLICABLE: ("Not Applicable"),
        }

        return labels[status]

    @staticmethod
    def _centred_item(
        value: str,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    @staticmethod
    def _refresh_status_style(
        label: QLabel,
    ) -> None:
        label.style().unpolish(label)
        label.style().polish(label)
