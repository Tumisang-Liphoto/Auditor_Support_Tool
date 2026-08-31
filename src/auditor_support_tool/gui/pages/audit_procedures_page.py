"""Page for selecting and running audit procedures."""

from __future__ import annotations

import qtawesome as qta
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
)
from auditor_support_tool.core.procedure_availability import (
    ProcedureAvailabilityService,
)
from auditor_support_tool.core.procedure_dataset_resolution import (
    ProcedureDatasetBundle,
    ProcedureDatasetResolution,
    ProcedureDatasetSource,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
)
from auditor_support_tool.core.procedure_execution_status_service import (
    ProcedureExecutionStatus,
    ProcedureExecutionStatusService,
)
from auditor_support_tool.core.procedure_parameter_service import (
    ProcedureParameterValidationError,
    format_procedure_parameter_value,
    resolve_procedure_parameters,
)
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadiness,
    ProcedureReadinessService,
)
from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.core.test_description_catalogue import (
    has_test_description_document,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineStatus,
)
from auditor_support_tool.core.test_engine_service import (
    TestEngineService,
)
from auditor_support_tool.core.workbook_package import (
    DatasetType,
    FieldMappingStatus,
    WorksheetDataset,
)
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)
from auditor_support_tool.gui.dialogs.procedure_parameters_dialog import (
    ProcedureParametersDialog,
)


class AuditProceduresPage(QWidget):
    """Select and execute procedures available to the active workspace."""

    back_requested = Signal(str)
    result_ready = Signal(object)
    test_description_requested = Signal(str)

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
        self._availability_service = ProcedureAvailabilityService(
            readiness_service=self._readiness_service
        )
        self._test_engine = TestEngineService(registry=procedure_registry)
        self._execution_status_service = ProcedureExecutionStatusService()

        self._updating_dataset_selector = False

        self._build_interface()
        self._connect_signals()
        self._refresh_page()

    def _build_interface(self) -> None:
        """Build the Audit Procedures page."""

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

        self._back_button = QPushButton("Back to Field Mapping")
        self._back_button.setObjectName("secondaryActionButton")
        self._back_button.setIcon(qta.icon("fa5s.arrow-left"))

        navigation_layout.addWidget(self._back_button)
        navigation_layout.addStretch(1)

        title = QLabel("Audit Procedures")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Run audit procedures supported by the currently prepared and "
            "mapped data. Availability is checked automatically."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addLayout(navigation_layout)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_dataset_card())
        layout.addWidget(self._build_procedures_card())

        self._page_status = QLabel()
        self._page_status.setObjectName("formStatus")
        self._page_status.setWordWrap(True)
        self._page_status.setVisible(False)

        layout.addWidget(self._page_status)
        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_dataset_card(self) -> QFrame:
        """Create the active-dataset summary card."""

        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)

        heading = QLabel("Dataset")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "The active mapped dataset is selected automatically. "
            "Change it only when the workspace contains more than one dataset."
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

    def _build_procedures_card(self) -> QFrame:
        """Create the executable-procedure section."""

        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._procedures_layout = QVBoxLayout(card)
        self._procedures_layout.setContentsMargins(30, 24, 30, 24)
        self._procedures_layout.setSpacing(14)

        heading = QLabel("Available Procedures")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "Only implemented procedures whose required datasets and fields "
            "are available are shown. Optional fields may enrich results but "
            "do not block execution."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._procedures_container = QWidget()
        self._procedure_rows_layout = QVBoxLayout(self._procedures_container)
        self._procedure_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._procedure_rows_layout.setSpacing(10)

        self._procedures_layout.addWidget(heading)
        self._procedures_layout.addWidget(description)
        self._procedures_layout.addWidget(self._procedures_container)

        return card

    def _connect_signals(self) -> None:
        """Connect page and workspace signals."""

        self._back_button.clicked.connect(
            lambda: self.back_requested.emit("workspace.field_mapping")
        )
        self._dataset_selector.currentIndexChanged.connect(self._dataset_selection_changed)

        self._workspace_state.workbook_package_changed.connect(self._refresh_page)
        self._workspace_state.active_dataset_changed.connect(self._refresh_page)
        self._workspace_state.workspace_identity_changed.connect(self._refresh_page)
        self._workspace_state.procedure_parameters_changed.connect(
            lambda _procedure_id: self._refresh_page()
        )
        self._workspace_state.procedure_execution_changed.connect(
            lambda _procedure_id, _dataset_id: self._refresh_page()
        )
        self._workspace_state.workspace_cleared.connect(self._refresh_page)

    def _refresh_page(self) -> None:
        """Refresh datasets, readiness and procedure actions."""

        self._refresh_dataset_selector()
        self._clear_page_status()

        dataset = self._active_mapped_dataset()

        if dataset is None:
            self._dataset_summary.setText("No mapped dataset is available.")
            self._clear_procedure_rows()

            empty_label = QLabel("Complete Field Mapping before running audit procedures.")
            empty_label.setObjectName("fieldHint")
            empty_label.setWordWrap(True)
            self._procedure_rows_layout.addWidget(empty_label)
            return

        self._dataset_summary.setText(self._dataset_summary_text(dataset))
        self._populate_procedures(dataset)

    def _refresh_dataset_selector(self) -> None:
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

    def _populate_procedures(self, dataset: WorksheetDataset) -> None:
        """Display only procedures supported by the selected mapped data."""

        self._clear_procedure_rows()

        procedures = self._procedure_registry.procedures

        if not procedures:
            empty_label = QLabel("No executable audit procedures are currently registered.")
            empty_label.setObjectName("fieldHint")
            empty_label.setWordWrap(True)
            self._procedure_rows_layout.addWidget(empty_label)
            return

        source = PreparedAuditDataset(dataset)
        active_source = ProcedureDatasetSource.create(
            dataset_type=dataset.confirmed_dataset_type,
            source=source,
        )
        mapped_sources = self._procedure_dataset_sources()

        available = self._availability_service.available_for_workspace(
            procedures=procedures,
            active_source=active_source,
            mapped_sources=mapped_sources,
        )

        if not available:
            empty_label = QLabel("No audit procedures are available for the currently mapped data.")
            empty_label.setObjectName("fieldHint")
            empty_label.setWordWrap(True)
            self._procedure_rows_layout.addWidget(empty_label)
            return

        for item in available:
            execution_status = self._procedure_execution_status(
                definition=item.procedure.definition,
                source=source,
                dataset_resolution=item.dataset_resolution,
            )

            self._procedure_rows_layout.addWidget(
                self._build_procedure_row(
                    item.procedure.definition,
                    item.readiness,
                    execution_status,
                )
            )

    def _build_procedure_row(
        self,
        definition: ProcedureDefinition,
        readiness: ProcedureReadiness,
        execution_status: ProcedureExecutionStatus,
    ) -> QFrame:
        """Create one clearly separated procedure card with execution state."""

        row = QFrame()
        row.setObjectName("procedureCard")

        layout = QHBoxLayout(row)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(18)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(5)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        name_label = QLabel(f"{definition.display_id}  {definition.name}")
        name_label.setObjectName("fieldLabel")

        status_label = QLabel(self._execution_status_text(execution_status))
        status_label.setObjectName("procedureExecutionStatus")
        status_label.setProperty(
            "status",
            execution_status.value,
        )

        header_layout.addWidget(name_label)
        header_layout.addStretch(1)
        header_layout.addWidget(status_label)

        requirements_label = QLabel(self._readiness_message(readiness))
        requirements_label.setObjectName("fieldHint")
        requirements_label.setWordWrap(True)

        text_layout.addLayout(header_layout)
        text_layout.addWidget(requirements_label)

        if definition.parameter_definitions:
            settings_label = QLabel(self._parameter_summary(definition))
            settings_label.setObjectName("fieldHint")
            settings_label.setWordWrap(True)
            text_layout.addWidget(settings_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        description_button = QPushButton("Test Description")
        description_button.setObjectName("secondaryActionButton")
        description_button.setIcon(qta.icon("fa5s.book-open"))

        description_available = has_test_description_document(definition.procedure_id)
        description_button.setEnabled(description_available)

        if not description_available:
            description_button.setToolTip("A bundled test description is not yet available.")

        description_button.clicked.connect(
            lambda checked=False, selected_id=definition.procedure_id: (
                self.test_description_requested.emit(selected_id)
            )
        )
        actions_layout.addWidget(description_button)

        if definition.parameter_definitions:
            configure_button = QPushButton("Configure")
            configure_button.setObjectName("secondaryActionButton")
            configure_button.setIcon(qta.icon("fa5s.cog"))
            configure_button.clicked.connect(
                lambda checked=False, selected_id=definition.procedure_id: (
                    self._configure_procedure(selected_id)
                )
            )
            actions_layout.addWidget(configure_button)

        action_button = QPushButton(self._run_button_text(execution_status))
        action_button.setObjectName("primaryActionButton")
        action_button.setIcon(qta.icon("fa5s.play"))
        action_button.clicked.connect(
            lambda checked=False, selected_id=definition.procedure_id: self._run_procedure(
                selected_id
            )
        )

        actions_layout.addWidget(action_button)

        layout.addLayout(text_layout, 1)
        layout.addLayout(actions_layout)

        return row

    def _configure_procedure(self, procedure_id: str) -> None:
        """Open the generic settings dialog for one procedure."""

        procedure = self._procedure_registry.get(procedure_id)

        if procedure is None:
            self._set_page_status(
                f"No executable implementation is registered for {procedure_id}.",
                "error",
            )
            return

        definition = procedure.definition

        if not definition.parameter_definitions:
            self._set_page_status(
                "This procedure has no configurable settings.",
                "neutral",
            )
            return

        dialog = ProcedureParametersDialog(
            definition=definition,
            initial_values=self._workspace_state.get_procedure_parameters(procedure_id),
            parent=self,
        )

        if not dialog.exec():
            return

        try:
            self._workspace_state.set_procedure_parameters(
                procedure_id,
                dialog.parameter_values,
            )
        except (TypeError, ValueError) as error:
            self._set_page_status(str(error), "error")
            return

        self._set_page_status(
            f"Settings saved for {definition.display_id}.",
            "success",
        )

    def _run_procedure(self, procedure_id: str) -> None:
        """Run a ready procedure and send its outcome to the Results page."""

        dataset = self._active_mapped_dataset()
        source_path = self._workspace_state.source_path
        identity = self._workspace_state.workspace_identity

        if dataset is None:
            self._set_page_status(
                "No mapped dataset is available.",
                "error",
            )
            return

        if source_path is None:
            self._set_page_status(
                "The workspace source file is not available.",
                "error",
            )
            return

        if identity is None:
            self._set_page_status(
                "No active audit workspace is available.",
                "error",
            )
            return

        source = PreparedAuditDataset(dataset)

        procedure = self._procedure_registry.get(procedure_id)

        if procedure is None:
            self._set_page_status(
                f"No executable implementation is registered for {procedure_id}.",
                "error",
            )
            return

        try:
            effective_parameters = resolve_procedure_parameters(
                procedure.definition,
                self._workspace_state.get_procedure_parameters(procedure_id),
            )
            self._workspace_state.set_procedure_parameters(
                procedure_id,
                effective_parameters,
            )
        except (ProcedureParameterValidationError, TypeError, ValueError) as error:
            self._set_page_status(
                f"Review the procedure settings before running: {error}",
                "error",
            )
            return

        audit_period_start = str(getattr(identity, "audit_period_start", "") or "")
        audit_period_end = str(getattr(identity, "audit_period_end", "") or "")

        self._set_page_status(
            "Running audit procedure...",
            "neutral",
        )

        outcome = self._test_engine.run(
            procedure_id=procedure_id,
            source=source,
            source_path=source_path,
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            parameters=effective_parameters,
            dataset_sources=self._procedure_dataset_sources(),
        )

        if outcome.status == TestEngineStatus.COMPLETED and outcome.result is not None:
            self._execution_status_service.remember_source_hash(
                source_path,
                outcome.result.context.source_sha256,
            )
            self._workspace_state.record_procedure_execution(
                ProcedureExecutionStamp.from_context(outcome.result.context)
            )

        self._clear_page_status()
        self.result_ready.emit(outcome)

    def _procedure_execution_status(
        self,
        *,
        definition: ProcedureDefinition,
        source: PreparedAuditDataset,
        dataset_resolution: ProcedureDatasetResolution | None = None,
    ) -> ProcedureExecutionStatus:
        """Return execution state for the current procedure and dataset."""

        stamp = self._workspace_state.get_procedure_execution_stamp(
            definition.procedure_id,
            source.dataset_id,
        )

        if stamp is None:
            return ProcedureExecutionStatus.NOT_RUN

        source_path = self._workspace_state.source_path
        identity = self._workspace_state.workspace_identity

        if source_path is None or identity is None:
            return ProcedureExecutionStatus.NEEDS_RERUN

        try:
            effective_parameters = resolve_procedure_parameters(
                definition,
                self._workspace_state.get_procedure_parameters(definition.procedure_id),
            )
        except (
            ProcedureParameterValidationError,
            TypeError,
            ValueError,
        ):
            return ProcedureExecutionStatus.NEEDS_RERUN

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

        status_source = source

        if definition.uses_dataset_requirements:
            if dataset_resolution is None or not dataset_resolution.complete:
                return ProcedureExecutionStatus.NEEDS_RERUN

            try:
                status_source = ProcedureDatasetBundle.create(dataset_resolution)
            except ValueError:
                return ProcedureExecutionStatus.NEEDS_RERUN

        return self._execution_status_service.evaluate(
            definition=definition,
            source=status_source,
            source_path=source_path,
            parameters=effective_parameters,
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            stamp=stamp,
        )

    def _dataset_selection_changed(self, index: int) -> None:
        """Change the active dataset when the auditor selects another one."""

        if self._updating_dataset_selector or index < 0:
            return

        dataset_id = self._dataset_selector.itemData(index)

        if not isinstance(dataset_id, str):
            return

        try:
            self._workspace_state.set_active_dataset(dataset_id)
        except ValueError as error:
            self._set_page_status(str(error), "error")
            return

        self._clear_page_status()

    def _active_mapped_dataset(self) -> WorksheetDataset | None:
        """Return the active dataset when mapping is complete."""

        dataset = self._workspace_state.active_dataset

        if (
            dataset is None
            or not dataset.selected
            or dataset.mapping_status not in self._MAPPING_COMPLETE
        ):
            return None

        return dataset

    def _mapped_datasets(self) -> tuple[WorksheetDataset, ...]:
        """Return selected datasets whose mapping stage is complete."""

        return tuple(
            dataset
            for dataset in self._workspace_state.selected_datasets
            if dataset.mapping_status in self._MAPPING_COMPLETE
        )

    def _procedure_dataset_sources(
        self,
    ) -> tuple[ProcedureDatasetSource, ...]:
        """Return mapped datasets with generic type metadata for the Test Engine."""

        return tuple(
            ProcedureDatasetSource.create(
                dataset_type=dataset.confirmed_dataset_type,
                source=PreparedAuditDataset(dataset),
            )
            for dataset in self._mapped_datasets()
            if dataset.confirmed_dataset_type != DatasetType.UNCLASSIFIED
        )

    def _parameter_summary(
        self,
        definition: ProcedureDefinition,
    ) -> str:
        """Return a concise summary of configured and default settings."""

        saved_values = self._workspace_state.get_procedure_parameters(definition.procedure_id)

        try:
            effective_values = resolve_procedure_parameters(
                definition,
                saved_values,
            )
        except ProcedureParameterValidationError as error:
            return f"Settings need review: {error}"

        parts: list[str] = []

        for parameter in definition.parameter_definitions:
            if parameter.key not in effective_values:
                parts.append(f"{parameter.label}: Not configured")
                continue

            value_text = format_procedure_parameter_value(
                parameter,
                effective_values[parameter.key],
            )
            default_suffix = (
                " (default)"
                if parameter.key not in saved_values and parameter.default_value is not None
                else ""
            )
            parts.append(f"{parameter.label}: {value_text}{default_suffix}")

        return "Settings: " + " | ".join(parts)

    def _set_page_status(
        self,
        message: str,
        status: str,
    ) -> None:
        """Show a concise page-level execution message."""

        self._page_status.setText(message)
        self._page_status.setProperty("status", status)
        self._page_status.setVisible(True)
        self._refresh_status_style(self._page_status)

    def _clear_page_status(self) -> None:
        """Clear the page-level execution message."""

        self._page_status.clear()
        self._page_status.setVisible(False)

    @staticmethod
    def _dataset_summary_text(dataset: WorksheetDataset) -> str:
        """Return a concise active-dataset description."""

        return (
            f"Dataset: {dataset.confirmed_display_name} "
            f"| Worksheet: {dataset.original_worksheet_name} "
            f"| Records: {dataset.loaded_table.record_count:,}"
        )

    @staticmethod
    def _readiness_message(readiness: ProcedureReadiness) -> str:
        """Return concise field-readiness information."""

        if readiness.dataset_readiness:
            parts = []

            for dataset in readiness.dataset_readiness:
                dataset_name = dataset.dataset_type.value.replace("_", " ").title()

                if not dataset.resolved:
                    parts.append(f"{dataset_name}: unavailable")
                    continue

                fields = ", ".join(dataset.mapped_required_fields)

                if fields:
                    parts.append(f"{dataset_name}: {fields}")
                else:
                    parts.append(f"{dataset_name}: available")

            if readiness.warnings:
                return " | ".join(parts) + " | " + " ".join(readiness.warnings)

            return "Required datasets available: " + " | ".join(parts)

        if readiness.missing_required_fields:
            return "Missing required field mapping: " + ", ".join(readiness.missing_required_fields)

        if readiness.warnings:
            return " ".join(readiness.warnings)

        if readiness.mapped_required_fields:
            return "Required fields available: " + ", ".join(readiness.mapped_required_fields)

        return "No additional required fields."

    @staticmethod
    def _execution_status_text(
        status: ProcedureExecutionStatus,
    ) -> str:
        """Return the concise procedure execution badge."""

        labels = {
            ProcedureExecutionStatus.NOT_RUN: "Not Run",
            ProcedureExecutionStatus.COMPLETED: "✓ Completed",
            ProcedureExecutionStatus.NEEDS_RERUN: "↻ Needs Re-run",
        }

        return labels[status]

    @staticmethod
    def _run_button_text(
        status: ProcedureExecutionStatus,
    ) -> str:
        """Return the appropriate action for the current execution state."""

        if status == ProcedureExecutionStatus.NOT_RUN:
            return "Run Test"

        if status == ProcedureExecutionStatus.NEEDS_RERUN:
            return "Re-run Test"

        return "Run Again"

    def _clear_procedure_rows(self) -> None:
        """Remove all existing procedure rows."""

        while self._procedure_rows_layout.count():
            item = self._procedure_rows_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _refresh_status_style(label: QLabel) -> None:
        """Refresh a dynamic status property."""

        label.style().unpolish(label)
        label.style().polish(label)
