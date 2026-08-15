"""Page for selecting and running audit procedures."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
)
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadiness,
    ProcedureReadinessService,
    ProcedureReadinessStatus,
)
from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineOutcome,
    TestEngineStatus,
)
from auditor_support_tool.core.test_engine_service import (
    TestEngineService,
)
from auditor_support_tool.core.workbook_package import (
    FieldMappingStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)


class AuditProceduresPage(QWidget):
    """Select and execute procedures available to the active workspace."""

    back_requested = Signal(str)

    _MAPPING_COMPLETE = {
        FieldMappingStatus.CONFIRMED,
        FieldMappingStatus.CONFIRMED_WITH_WARNINGS,
        FieldMappingStatus.NOT_APPLICABLE,
    }

    def __init__(
        self,
        *,
        workspace_state: WorkspaceState,
        procedure_registry: ProcedureRegistry,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state
        self._procedure_registry = procedure_registry

        self._readiness_service = ProcedureReadinessService()
        self._test_engine = TestEngineService(registry=procedure_registry)

        self._updating_dataset_selector = False

        self._build_interface()
        self._connect_signals()
        self._refresh_page()

    def _build_interface(self) -> None:
        """Build the Audit Procedures page."""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            40,
            32,
            40,
            32,
        )
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        navigation_layout = QHBoxLayout()

        self._back_button = QPushButton("Back to Field Mapping")
        self._back_button.setObjectName("secondaryActionButton")

        navigation_layout.addWidget(self._back_button)
        navigation_layout.addStretch(1)

        title = QLabel("Audit Procedures")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Run audit procedures against the prepared "
            "and mapped dataset. Readiness is checked "
            "automatically."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addLayout(navigation_layout)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        layout.addWidget(self._build_dataset_card())
        layout.addWidget(self._build_procedures_card())
        layout.addWidget(self._build_results_card())

        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_dataset_card(
        self,
    ) -> QFrame:
        """Create the active-dataset summary card."""

        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            30,
            24,
            30,
            24,
        )
        layout.setSpacing(12)

        heading = QLabel("Dataset")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "The active mapped dataset is selected "
            "automatically. Change it only when the "
            "workspace contains more than one dataset."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._dataset_selector = QComboBox()
        self._dataset_selector.setEnabled(False)

        self._dataset_summary = QLabel("No mapped dataset is available.")
        self._dataset_summary.setObjectName("fieldHint")
        self._dataset_summary.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._dataset_selector)
        layout.addWidget(self._dataset_summary)

        return card

    def _build_procedures_card(
        self,
    ) -> QFrame:
        """Create the executable-procedure section."""

        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._procedures_layout = QVBoxLayout(card)
        self._procedures_layout.setContentsMargins(
            30,
            24,
            30,
            24,
        )
        self._procedures_layout.setSpacing(14)

        heading = QLabel("Available Procedures")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Only procedures with executable implementations "
            "are shown here. Required-field checks are performed "
            "automatically against the selected dataset."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._procedures_container = QWidget()
        self._procedure_rows_layout = QVBoxLayout(self._procedures_container)
        self._procedure_rows_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self._procedure_rows_layout.setSpacing(10)

        self._procedures_layout.addWidget(heading)
        self._procedures_layout.addWidget(description)
        self._procedures_layout.addWidget(self._procedures_container)

        return card

    def _build_results_card(
        self,
    ) -> QFrame:
        """Create the result-summary section."""

        self._results_card = QFrame()
        self._results_card.setObjectName("profileSectionCard")
        self._results_card.setVisible(False)

        layout = QVBoxLayout(self._results_card)
        layout.setContentsMargins(
            30,
            24,
            30,
            24,
        )
        layout.setSpacing(14)

        self._results_heading = QLabel("Procedure Result")
        self._results_heading.setObjectName("profileSectionTitle")

        self._result_status = QLabel()
        self._result_status.setObjectName("formStatus")
        self._result_status.setWordWrap(True)

        self._result_summary = QLabel()
        self._result_summary.setObjectName("profileSectionDescription")
        self._result_summary.setWordWrap(True)

        exceptions_heading = QLabel("Exceptions")
        exceptions_heading.setObjectName("fieldLabel")

        self._exceptions_table = QTableWidget()
        self._exceptions_table.setColumnCount(4)
        self._exceptions_table.setHorizontalHeaderLabels(
            (
                "Source Row",
                "Reason",
                "Record ID",
                "Details",
            )
        )
        self._exceptions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._exceptions_table.setAlternatingRowColors(True)
        self._exceptions_table.verticalHeader().setVisible(False)

        header = self._exceptions_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        layout.addWidget(self._results_heading)
        layout.addWidget(self._result_status)
        layout.addWidget(self._result_summary)
        layout.addWidget(exceptions_heading)
        layout.addWidget(self._exceptions_table)

        return self._results_card

    def _connect_signals(
        self,
    ) -> None:
        """Connect page and workspace signals."""

        self._back_button.clicked.connect(
            lambda: self.back_requested.emit("workspace.field_mapping")
        )

        self._dataset_selector.currentIndexChanged.connect(self._dataset_selection_changed)

        self._workspace_state.workbook_package_changed.connect(self._refresh_page)
        self._workspace_state.active_dataset_changed.connect(self._refresh_page)
        self._workspace_state.workspace_identity_changed.connect(self._refresh_page)
        self._workspace_state.workspace_cleared.connect(self._refresh_page)

    def _refresh_page(
        self,
    ) -> None:
        """Refresh datasets, readiness and procedure actions."""

        self._refresh_dataset_selector()

        dataset = self._active_mapped_dataset()

        if dataset is None:
            self._dataset_summary.setText("No mapped dataset is available.")
            self._clear_procedure_rows()

            empty_label = QLabel("Complete Field Mapping before running audit procedures.")
            empty_label.setObjectName("fieldHint")
            empty_label.setWordWrap(True)

            self._procedure_rows_layout.addWidget(empty_label)

            self._results_card.setVisible(False)
            return

        self._dataset_summary.setText(self._dataset_summary_text(dataset))

        self._populate_procedures(dataset)

    def _refresh_dataset_selector(
        self,
    ) -> None:
        """Refresh mapped datasets and retain the active dataset."""

        datasets = self._mapped_datasets()
        active_dataset_id = self._workspace_state.active_dataset_id

        self._updating_dataset_selector = True

        try:
            self._dataset_selector.clear()

            for dataset in datasets:
                self._dataset_selector.addItem(
                    dataset.confirmed_display_name,
                    dataset.dataset_id,
                )

            active_index = self._dataset_selector.findData(active_dataset_id)

            if active_index >= 0:
                self._dataset_selector.setCurrentIndex(active_index)
            elif self._dataset_selector.count() > 0:
                self._dataset_selector.setCurrentIndex(0)

            self._dataset_selector.setEnabled(self._dataset_selector.count() > 1)
        finally:
            self._updating_dataset_selector = False

    def _populate_procedures(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        """Display executable procedures and their current readiness."""

        self._clear_procedure_rows()

        procedures = self._procedure_registry.procedures

        if not procedures:
            empty_label = QLabel("No executable audit procedures are currently registered.")
            empty_label.setObjectName("fieldHint")
            self._procedure_rows_layout.addWidget(empty_label)
            return

        source = PreparedAuditDataset(dataset)

        for procedure in procedures:
            readiness = self._readiness_service.check(
                definition=procedure.definition,
                source=source,
            )

            self._procedure_rows_layout.addWidget(
                self._build_procedure_row(
                    procedure.definition.procedure_id,
                    procedure.definition.display_id,
                    procedure.definition.name,
                    readiness,
                )
            )

    def _build_procedure_row(
        self,
        procedure_id: str,
        display_id: str,
        name: str,
        readiness: ProcedureReadiness,
    ) -> QFrame:
        """Create one procedure row with a direct action."""

        row = QFrame()
        row.setObjectName("datasetMappingStatusRow")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(
            14,
            12,
            14,
            12,
        )
        layout.setSpacing(14)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        name_label = QLabel(f"{display_id}  {name}")
        name_label.setObjectName("fieldLabel")

        requirements_label = QLabel(self._readiness_message(readiness))
        requirements_label.setObjectName("fieldHint")
        requirements_label.setWordWrap(True)

        text_layout.addWidget(name_label)
        text_layout.addWidget(requirements_label)

        status_label = QLabel(self._readiness_status_text(readiness.status))
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setMinimumWidth(150)
        status_label.setStyleSheet(self._readiness_badge_style(readiness.status))

        if readiness.can_run:
            action_button = QPushButton("Run Test")
            action_button.setObjectName("primaryActionButton")
            action_button.clicked.connect(
                lambda checked=False, selected_id=procedure_id: self._run_procedure(selected_id)
            )
        else:
            action_button = QPushButton("Review Field Mapping")
            action_button.setObjectName("secondaryActionButton")
            action_button.clicked.connect(
                lambda: self.back_requested.emit("workspace.field_mapping")
            )

        layout.addLayout(
            text_layout,
            1,
        )
        layout.addWidget(status_label)
        layout.addWidget(action_button)

        return row

    def _run_procedure(
        self,
        procedure_id: str,
    ) -> None:
        """Run a ready procedure using workspace information automatically."""

        dataset = self._active_mapped_dataset()
        source_path = self._workspace_state.source_path
        identity = self._workspace_state.workspace_identity

        if dataset is None:
            self._show_failure("No mapped dataset is available.")
            return

        if source_path is None:
            self._show_failure("The workspace source file is not available.")
            return

        if identity is None:
            self._show_failure("No active audit workspace is available.")
            return

        source = PreparedAuditDataset(dataset)

        audit_period_start = str(
            getattr(
                identity,
                "audit_period_start",
                "",
            )
            or ""
        )
        audit_period_end = str(
            getattr(
                identity,
                "audit_period_end",
                "",
            )
            or ""
        )

        outcome = self._test_engine.run(
            procedure_id=procedure_id,
            source=source,
            source_path=source_path,
            audit_period_start=(audit_period_start),
            audit_period_end=(audit_period_end),
        )

        self._display_outcome(outcome)

    def _display_outcome(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Display an engine outcome immediately on the page."""

        self._results_card.setVisible(True)

        if outcome.status != TestEngineStatus.COMPLETED or outcome.result is None:
            self._show_failure(
                outcome.error_message or self._outcome_failure_message(outcome.status)
            )
            return

        result = outcome.result

        procedure = self._procedure_registry.require(outcome.procedure_id)

        self._results_heading.setText(
            f"{procedure.definition.display_id} {procedure.definition.name}"
        )

        self._result_status.setText("Procedure completed successfully.")
        self._result_status.setProperty(
            "status",
            "success",
        )
        self._refresh_status_style(self._result_status)

        summary_parts = [
            (f"Population: {result.population_count:,}"),
            (f"Evaluated: {result.records_evaluated_count:,}"),
            (f"Excluded: {result.excluded_record_count:,}"),
            (f"Exceptions: {result.exception_count:,}"),
            (f"Exception rate: {result.exception_rate:.2f}%"),
        ]

        self._result_summary.setText("   |   ".join(summary_parts))

        self._populate_exception_table(result.exception_records)

    def _show_failure(
        self,
        message: str,
    ) -> None:
        """Display a controlled procedure failure."""

        self._results_card.setVisible(True)
        self._results_heading.setText("Procedure Result")
        self._result_status.setText(message)
        self._result_status.setProperty(
            "status",
            "error",
        )
        self._refresh_status_style(self._result_status)
        self._result_summary.clear()
        self._exceptions_table.clearContents()
        self._exceptions_table.setRowCount(0)

    def _populate_exception_table(
        self,
        exception_records,
    ) -> None:
        """Populate detailed exceptions from a procedure result."""

        self._exceptions_table.clearContents()
        self._exceptions_table.setRowCount(len(exception_records))

        for row_number, exception in enumerate(exception_records):
            source_row = QTableWidgetItem(str(exception.source_row_number))
            source_row.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            reason = QTableWidgetItem(exception.reason)

            record_id = QTableWidgetItem(exception.source_record_id)

            detail_text = ", ".join(f"{key}={value}" for key, value in (exception.values.items()))

            details = QTableWidgetItem(detail_text or "—")
            details.setToolTip(detail_text)

            self._exceptions_table.setItem(
                row_number,
                0,
                source_row,
            )
            self._exceptions_table.setItem(
                row_number,
                1,
                reason,
            )
            self._exceptions_table.setItem(
                row_number,
                2,
                record_id,
            )
            self._exceptions_table.setItem(
                row_number,
                3,
                details,
            )

        visible_rows = min(
            max(
                len(exception_records),
                1,
            ),
            12,
        )

        row_height = self._exceptions_table.verticalHeader().defaultSectionSize()

        header_height = self._exceptions_table.horizontalHeader().height()

        self._exceptions_table.setMinimumHeight(header_height + visible_rows * row_height + 12)

    def _dataset_selection_changed(
        self,
        index: int,
    ) -> None:
        """Change the active dataset when the auditor selects another one."""

        if self._updating_dataset_selector or index < 0:
            return

        dataset_id = self._dataset_selector.itemData(index)

        if not isinstance(
            dataset_id,
            str,
        ):
            return

        try:
            self._workspace_state.set_active_dataset(dataset_id)
        except ValueError:
            return

        self._results_card.setVisible(False)

    def _active_mapped_dataset(
        self,
    ) -> WorksheetDataset | None:
        """Return the active dataset when mapping is complete."""

        dataset = self._workspace_state.active_dataset

        if (
            dataset is None
            or not dataset.selected
            or dataset.mapping_status not in self._MAPPING_COMPLETE
        ):
            return None

        return dataset

    def _mapped_datasets(
        self,
    ) -> tuple[WorksheetDataset, ...]:
        """Return selected datasets whose mapping stage is complete."""

        return tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.mapping_status in self._MAPPING_COMPLETE
        )

    @staticmethod
    def _dataset_summary_text(
        dataset: WorksheetDataset,
    ) -> str:
        """Return a concise active-dataset description."""

        return (
            f"Dataset: "
            f"{dataset.confirmed_display_name} "
            f"| Worksheet: "
            f"{dataset.original_worksheet_name} "
            f"| Records: "
            f"{dataset.loaded_table.record_count:,}"
        )

    @staticmethod
    def _readiness_message(
        readiness: ProcedureReadiness,
    ) -> str:
        """Return concise field-readiness information."""

        if readiness.missing_required_fields:
            return "Missing required field mapping: " + ", ".join(readiness.missing_required_fields)

        if readiness.warnings:
            return " ".join(readiness.warnings)

        if readiness.mapped_required_fields:
            return "Required fields available: " + ", ".join(readiness.mapped_required_fields)

        return "No additional required fields."

    @staticmethod
    def _readiness_status_text(
        status: ProcedureReadinessStatus,
    ) -> str:
        """Return the user-facing readiness label."""

        labels = {
            ProcedureReadinessStatus.READY: ("Ready"),
            ProcedureReadinessStatus.READY_WITH_WARNING: ("Ready with Warning"),
            ProcedureReadinessStatus.BLOCKED: ("Blocked"),
        }

        return labels[status]

    @staticmethod
    def _readiness_badge_style(
        status: ProcedureReadinessStatus,
    ) -> str:
        """Return simple readiness badge styling."""

        if status == ProcedureReadinessStatus.READY:
            background = "#198754"
        elif status == ProcedureReadinessStatus.READY_WITH_WARNING:
            background = "#d18b00"
        else:
            background = "#c62828"

        return (
            f"background-color: {background};"
            "color: white;"
            "border-radius: 5px;"
            "padding: 6px 10px;"
            "font-weight: 600;"
        )

    @staticmethod
    def _outcome_failure_message(
        status: TestEngineStatus,
    ) -> str:
        """Return a clear message for non-completed engine states."""

        messages = {
            TestEngineStatus.NOT_IMPLEMENTED: ("This procedure is not implemented."),
            TestEngineStatus.BLOCKED: ("The procedure is blocked by missing required fields."),
            TestEngineStatus.CANCELLED: ("The procedure was cancelled."),
            TestEngineStatus.FAILED: ("The procedure could not be completed."),
        }

        return messages.get(
            status,
            "The procedure did not complete.",
        )

    def _clear_procedure_rows(
        self,
    ) -> None:
        """Remove all existing procedure rows."""

        while self._procedure_rows_layout.count():
            item = self._procedure_rows_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _refresh_status_style(
        label: QLabel,
    ) -> None:
        """Refresh a dynamic status property."""

        label.style().unpolish(label)
        label.style().polish(label)
