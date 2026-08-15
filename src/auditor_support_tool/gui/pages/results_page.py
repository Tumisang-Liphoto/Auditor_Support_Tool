"""Reusable audit procedure results page."""

from __future__ import annotations

from datetime import date, datetime

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineOutcome,
    TestEngineStatus,
)
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)


class ResultMetricCard(QFrame):
    """Reusable compact metric card."""

    def __init__(
        self,
        *,
        title: str,
        value: str,
        detail: str,
        icon_name: str,
        emphasis: str = "normal",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("resultMetricCard")
        self.setProperty(
            "emphasis",
            emphasis,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )
        layout.setSpacing(8)

        heading_layout = QHBoxLayout()
        heading_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        heading_layout.setSpacing(8)

        icon = QLabel()
        icon.setObjectName("resultMetricIcon")
        icon.setPixmap(
            qta.icon(
                icon_name,
                color="#2F6DB3",
            ).pixmap(
                QSize(
                    18,
                    18,
                )
            )
        )

        title_label = QLabel(title)
        title_label.setObjectName("resultMetricTitle")

        heading_layout.addWidget(icon)
        heading_layout.addWidget(title_label)
        heading_layout.addStretch(1)

        value_label = QLabel(value)
        value_label.setObjectName("resultMetricValue")
        value_label.setProperty(
            "emphasis",
            emphasis,
        )
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detail_label = QLabel(detail)
        detail_label.setObjectName("resultMetricDetail")
        detail_label.setWordWrap(True)
        detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(heading_layout)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)
        layout.addStretch(1)


class ResultsPage(QWidget):
    """Display the outcome of an executed audit procedure."""

    back_requested = Signal(str)
    export_requested = Signal(object)

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
        self._outcome: TestEngineOutcome | None = None
        self._procedure_breadcrumb_title = "Procedure"

        self._build_interface()
        self._show_empty_state()

    @property
    def procedure_breadcrumb_title(
        self,
    ) -> str:
        """Return the current procedure title for breadcrumbs."""

        return self._procedure_breadcrumb_title

    @property
    def outcome(
        self,
    ) -> TestEngineOutcome | None:
        """Return the currently displayed execution outcome."""

        return self._outcome

    def set_outcome(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Display a Test Engine outcome."""

        self._outcome = outcome

        procedure = self._procedure_registry.require(outcome.procedure_id)

        self._procedure_breadcrumb_title = (
            f"{procedure.definition.display_id} {procedure.definition.name}"
        )

        self._populate_header(outcome)
        self._populate_metadata(outcome)
        self._populate_metrics(outcome)
        self._populate_exceptions(outcome)

        self._empty_state.setVisible(False)
        self._result_content.setVisible(True)

    def clear_result(self) -> None:
        """Clear the current result."""

        self._outcome = None
        self._procedure_breadcrumb_title = "Procedure"
        self._show_empty_state()

    def _build_interface(self) -> None:
        """Build the reusable results page."""

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
            32,
            20,
            32,
            28,
        )
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addLayout(self._build_action_bar())

        self._empty_state = self._build_empty_state()
        layout.addWidget(self._empty_state)

        self._result_content = QWidget()
        self._result_content.setObjectName("resultsContent")

        result_layout = QVBoxLayout(self._result_content)
        result_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        result_layout.setSpacing(14)

        result_layout.addWidget(self._build_header_card())
        result_layout.addWidget(self._build_metadata_strip())
        result_layout.addLayout(self._build_metric_row())
        result_layout.addWidget(self._build_analysis_placeholder())
        result_layout.addWidget(self._build_exception_section())

        layout.addWidget(self._result_content)
        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_action_bar(
        self,
    ) -> QHBoxLayout:
        """Build the result-page action bar."""

        layout = QHBoxLayout()
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(8)

        back_button = QPushButton("Back to Procedures")
        back_button.setObjectName("secondaryActionButton")
        back_button.setIcon(qta.icon("fa5s.arrow-left"))
        back_button.clicked.connect(lambda: self.back_requested.emit("workspace.audit_procedures"))

        self._export_button = QPushButton("Export Result")
        self._export_button.setObjectName("secondaryActionButton")
        self._export_button.setIcon(qta.icon("fa5s.download"))
        self._export_button.setEnabled(False)
        self._export_button.setToolTip(
            "Result export will be enabled when export support is added."
        )
        self._export_button.clicked.connect(self._emit_export_requested)

        more_button = QToolButton()
        more_button.setObjectName("resultMoreButton")
        more_button.setIcon(qta.icon("fa5s.ellipsis-h"))
        more_button.setToolTip("Additional result actions")
        more_button.setEnabled(False)

        layout.addWidget(back_button)
        layout.addStretch(1)
        layout.addWidget(self._export_button)
        layout.addWidget(more_button)

        return layout

    def _build_empty_state(
        self,
    ) -> QFrame:
        """Create the empty Results page state."""

        frame = QFrame()
        frame.setObjectName("resultsEmptyState")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            28,
            32,
            28,
            32,
        )
        layout.setSpacing(8)

        heading = QLabel("No procedure result selected")
        heading.setObjectName("profileSectionTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        detail = QLabel(
            "Run an audit procedure to view "
            "its analysis, risk indicators "
            "and supporting transactions."
        )
        detail.setObjectName("profileSectionDescription")
        detail.setWordWrap(True)
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(heading)
        layout.addWidget(detail)

        return frame

    def _build_header_card(
        self,
    ) -> QFrame:
        """Create the procedure result header."""

        frame = QFrame()
        frame.setObjectName("resultHeader")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            10,
            4,
            10,
            4,
        )
        layout.setSpacing(7)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        title_layout.setSpacing(10)

        self._status_badge = QLabel("Completed")
        self._status_badge.setObjectName("resultStatusBadge")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._procedure_title = QLabel("Procedure Result")
        self._procedure_title.setObjectName("resultProcedureTitle")

        title_layout.addWidget(self._status_badge)
        title_layout.addWidget(self._procedure_title)
        title_layout.addStretch(1)

        self._procedure_description = QLabel()
        self._procedure_description.setObjectName("resultProcedureDescription")
        self._procedure_description.setWordWrap(True)

        layout.addLayout(title_layout)
        layout.addWidget(self._procedure_description)

        return frame

    def _build_metadata_strip(
        self,
    ) -> QFrame:
        """Create the compact execution metadata strip."""

        frame = QFrame()
        frame.setObjectName("resultMetadataStrip")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            10,
            8,
            10,
            8,
        )
        layout.setSpacing(0)

        self._metadata_dataset = QLabel()
        self._metadata_worksheet = QLabel()
        self._metadata_records = QLabel()
        self._metadata_period = QLabel()
        self._metadata_executed = QLabel()

        metadata_items = (
            (
                self._metadata_dataset,
                "fa5s.database",
            ),
            (
                self._metadata_worksheet,
                "fa5s.file-alt",
            ),
            (
                self._metadata_records,
                "fa5s.list-ol",
            ),
            (
                self._metadata_period,
                "fa5s.calendar-alt",
            ),
            (
                self._metadata_executed,
                "fa5s.clock",
            ),
        )

        for index, (
            label,
            icon_name,
        ) in enumerate(metadata_items):
            item = QWidget()
            item.setObjectName("resultMetadataItem")

            item_layout = QHBoxLayout(item)
            item_layout.setContentsMargins(
                10,
                0,
                10,
                0,
            )
            item_layout.setSpacing(6)

            icon = QLabel()
            icon.setPixmap(
                qta.icon(
                    icon_name,
                    color="#67756A",
                ).pixmap(
                    QSize(
                        14,
                        14,
                    )
                )
            )

            label.setObjectName("resultMetadataText")

            item_layout.addWidget(icon)
            item_layout.addWidget(label)

            layout.addWidget(item)

            if index < (len(metadata_items) - 1):
                divider = QFrame()
                divider.setObjectName("resultMetadataDivider")
                divider.setFrameShape(QFrame.Shape.VLine)
                layout.addWidget(divider)

        layout.addStretch(1)

        return frame

    def _build_metric_row(
        self,
    ) -> QHBoxLayout:
        """Create reusable headline metric cards."""

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self._population_card = ResultMetricCard(
            title="Population",
            value="—",
            detail="Source records",
            icon_name="fa5s.database",
        )

        self._evaluated_card = ResultMetricCard(
            title="Evaluated",
            value="—",
            detail="Records evaluated",
            icon_name="fa5s.check-circle",
            emphasis="success",
        )

        self._exceptions_card = ResultMetricCard(
            title="Exceptions",
            value="—",
            detail="Records requiring review",
            icon_name="fa5s.exclamation-triangle",
            emphasis="risk",
        )

        self._exception_rate_card = ResultMetricCard(
            title="Exception %",
            value="—",
            detail="Of evaluated records",
            icon_name="fa5s.percentage",
            emphasis="information",
        )

        self._metric_cards = (
            self._population_card,
            self._evaluated_card,
            self._exceptions_card,
            self._exception_rate_card,
        )

        for card in self._metric_cards:
            layout.addWidget(
                card,
                1,
            )

        return layout

    def _build_analysis_placeholder(
        self,
    ) -> QFrame:
        """Reserve the reusable procedure-analysis area."""

        frame = QFrame()
        frame.setObjectName("resultAnalysisPanel")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )
        layout.setSpacing(6)

        heading = QLabel("Audit Analysis")
        heading.setObjectName("resultSectionTitle")

        self._analysis_text = QLabel(
            "Procedure-specific risk indicators, observations and summaries will appear here."
        )
        self._analysis_text.setObjectName("resultSectionDescription")
        self._analysis_text.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(self._analysis_text)

        return frame

    def _build_exception_section(
        self,
    ) -> QFrame:
        """Create the detailed exception drill-down section."""

        frame = QFrame()
        frame.setObjectName("resultExceptionPanel")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )
        layout.setSpacing(10)

        self._exceptions_heading = QLabel("Detailed Exceptions")
        self._exceptions_heading.setObjectName("resultSectionTitle")

        self._exceptions_description = QLabel(
            "Source-linked records identified by the audit procedure."
        )
        self._exceptions_description.setObjectName("resultSectionDescription")

        self._exceptions_table = QTableWidget()
        self._exceptions_table.setObjectName("resultExceptionTable")
        self._exceptions_table.setColumnCount(4)
        self._exceptions_table.setHorizontalHeaderLabels(
            (
                "Source Row",
                "Reason",
                "Record ID",
                "Details",
            )
        )
        self._exceptions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._exceptions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._exceptions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
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

        self._exceptions_table.setMinimumHeight(260)

        layout.addWidget(self._exceptions_heading)
        layout.addWidget(self._exceptions_description)
        layout.addWidget(self._exceptions_table)

        return frame

    def _populate_header(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Populate procedure title and status."""

        procedure = self._procedure_registry.require(outcome.procedure_id)

        self._procedure_title.setText(
            f"{procedure.definition.display_id}  {procedure.definition.name}"
        )

        description = procedure.definition.description or "Audit procedure execution result."

        self._procedure_description.setText(description)

        status_text = {
            TestEngineStatus.COMPLETED: ("Completed"),
            TestEngineStatus.FAILED: ("Failed"),
            TestEngineStatus.CANCELLED: ("Cancelled"),
            TestEngineStatus.BLOCKED: ("Blocked"),
            TestEngineStatus.NOT_IMPLEMENTED: ("Not Implemented"),
        }.get(
            outcome.status,
            outcome.status.value.replace(
                "_",
                " ",
            ).title(),
        )

        self._status_badge.setText(status_text)
        self._status_badge.setProperty(
            "status",
            outcome.status.value,
        )
        self._refresh_dynamic_style(self._status_badge)

    def _populate_metadata(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Populate dataset and execution metadata."""

        dataset = None

        package = self._workspace_state.workbook_package

        if package is not None:
            dataset = package.get_dataset(outcome.dataset_id)

        if dataset is not None:
            dataset_name = dataset.confirmed_display_name
            worksheet_name = dataset.original_worksheet_name
        else:
            dataset_name = outcome.dataset_id
            worksheet_name = "—"

        self._metadata_dataset.setText(f"Dataset: {dataset_name}")
        self._metadata_worksheet.setText(f"Worksheet: {worksheet_name}")

        result = outcome.result

        if result is not None:
            population = result.population_count
            context = result.context

            period_text = self._format_period(
                context.audit_period_start,
                context.audit_period_end,
            )
        else:
            population = 0
            period_text = "Not available"

        self._metadata_records.setText(f"Records: {population:,}")
        self._metadata_period.setText(f"Period: {period_text}")

        executed_text = "—"

        if outcome.execution is not None:
            finished_at = getattr(
                outcome.execution,
                "finished_at",
                None,
            )

            executed_text = self._format_datetime(finished_at)

        self._metadata_executed.setText(f"Executed: {executed_text}")

    def _populate_metrics(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Populate generic result metric cards."""

        result = outcome.result

        if result is None:
            self._set_metric_card(
                self._population_card,
                "—",
                "No result population",
            )
            self._set_metric_card(
                self._evaluated_card,
                "—",
                "No records evaluated",
            )
            self._set_metric_card(
                self._exceptions_card,
                "—",
                "No exception result",
            )
            self._set_metric_card(
                self._exception_rate_card,
                "—",
                "No exception rate",
            )

            self._analysis_text.setText(
                outcome.error_message or "The procedure did not produce a completed result."
            )
            return

        self._set_metric_card(
            self._population_card,
            f"{result.population_count:,}",
            "Source records",
        )
        self._set_metric_card(
            self._evaluated_card,
            (f"{result.records_evaluated_count:,}"),
            "Records evaluated",
        )
        self._set_metric_card(
            self._exceptions_card,
            f"{result.exception_count:,}",
            "Records requiring review",
        )
        self._set_metric_card(
            self._exception_rate_card,
            f"{result.exception_rate:.2f}%",
            "Of evaluated records",
        )

        analysis_parts: list[str] = []

        if result.excluded_record_count:
            analysis_parts.append(
                f"{result.excluded_record_count:,} records were excluded from evaluation."
            )

        if result.limitations:
            analysis_parts.extend(result.limitations)

        if not analysis_parts:
            analysis_parts.append("The procedure completed without recorded execution limitations.")

        self._analysis_text.setText(" ".join(analysis_parts))

    def _populate_exceptions(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Populate source-linked procedure exceptions."""

        self._exceptions_table.clearContents()

        result = outcome.result

        if result is None:
            self._exceptions_table.setRowCount(0)
            self._exceptions_heading.setText("Detailed Exceptions")
            return

        exceptions = result.exception_records

        self._exceptions_heading.setText(
            f"{result.exception_count:,} Exception" + ("" if result.exception_count == 1 else "s")
        )

        self._exceptions_table.setRowCount(len(exceptions))

        for row_number, exception in enumerate(exceptions):
            source_row_item = QTableWidgetItem(str(exception.source_row_number))
            source_row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            reason_item = QTableWidgetItem(exception.reason)

            record_id_item = QTableWidgetItem(exception.source_record_id)

            detail_text = ", ".join(f"{key}={value}" for key, value in (exception.values.items()))

            details_item = QTableWidgetItem(detail_text or "—")
            details_item.setToolTip(detail_text)

            self._exceptions_table.setItem(
                row_number,
                0,
                source_row_item,
            )
            self._exceptions_table.setItem(
                row_number,
                1,
                reason_item,
            )
            self._exceptions_table.setItem(
                row_number,
                2,
                record_id_item,
            )
            self._exceptions_table.setItem(
                row_number,
                3,
                details_item,
            )

    def _show_empty_state(
        self,
    ) -> None:
        """Show the page before a result has been selected."""

        self._empty_state.setVisible(True)
        self._result_content.setVisible(False)

    def _emit_export_requested(
        self,
    ) -> None:
        """Emit the current result for future export handling."""

        if self._outcome is None:
            return

        self.export_requested.emit(self._outcome)

    @staticmethod
    def _set_metric_card(
        card: ResultMetricCard,
        value: str,
        detail: str,
    ) -> None:
        """Update a metric card's displayed values."""

        value_labels = card.findChildren(
            QLabel,
            "resultMetricValue",
        )
        detail_labels = card.findChildren(
            QLabel,
            "resultMetricDetail",
        )

        if value_labels:
            value_labels[0].setText(value)

        if detail_labels:
            detail_labels[0].setText(detail)

    @staticmethod
    def _format_period(
        start_value: str,
        end_value: str,
    ) -> str:
        """Return a concise audit-period label."""

        try:
            start = date.fromisoformat(start_value)
            end = date.fromisoformat(end_value)
        except ValueError:
            return "Not specified"

        return f"{start:%d %b %Y} - {end:%d %b %Y}"

    @staticmethod
    def _format_datetime(
        value: object,
    ) -> str:
        """Return a readable local execution timestamp."""

        parsed_value: datetime | None = None

        if isinstance(value, datetime):
            parsed_value = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed_value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return value

        if parsed_value is None:
            return "—"

        if parsed_value.tzinfo is not None:
            parsed_value = parsed_value.astimezone()

        return parsed_value.strftime("%d %b %Y, %H:%M")

    @staticmethod
    def _refresh_dynamic_style(
        widget: QWidget,
    ) -> None:
        """Refresh stylesheet selectors after property changes."""

        widget.style().unpolish(widget)
        widget.style().polish(widget)
