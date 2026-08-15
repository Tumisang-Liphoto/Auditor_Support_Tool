"""Reusable audit procedure results page."""

from __future__ import annotations

from datetime import date, datetime

import qtawesome as qta
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
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
from auditor_support_tool.presentation.result_dashboard_models import (
    DashboardIndicator,
    DashboardMetric,
    DashboardSummary,
    DashboardTable,
    DashboardTableRow,
    ResultDashboardPresentation,
)
from auditor_support_tool.presentation.result_presenter_registry import (
    present_result,
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

        self._icon = QLabel()
        self._icon.setObjectName("resultMetricIcon")

        self._title_label = QLabel()
        self._title_label.setObjectName("resultMetricTitle")

        heading_layout.addWidget(self._icon)
        heading_layout.addWidget(self._title_label)
        heading_layout.addStretch(1)

        self._value_label = QLabel()
        self._value_label.setObjectName("resultMetricValue")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._detail_label = QLabel()
        self._detail_label.setObjectName("resultMetricDetail")
        self._detail_label.setWordWrap(True)
        self._detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(heading_layout)
        layout.addWidget(self._value_label)
        layout.addWidget(self._detail_label)
        layout.addStretch(1)

        self.set_content(
            DashboardMetric(
                title=title,
                value=value,
                detail=detail,
                icon_name=icon_name,
                emphasis=emphasis,
            )
        )

    def set_content(
        self,
        metric: DashboardMetric,
    ) -> None:
        """Update all visible card content."""

        self.setProperty(
            "emphasis",
            metric.emphasis,
        )
        self._value_label.setProperty(
            "emphasis",
            metric.emphasis,
        )

        self._icon.setPixmap(
            qta.icon(
                metric.icon_name,
                color="#2F6DB3",
            ).pixmap(
                QSize(
                    18,
                    18,
                )
            )
        )
        self._title_label.setText(metric.title)
        self._value_label.setText(metric.value)
        self._detail_label.setText(metric.detail)

        self._refresh_style(self)
        self._refresh_style(self._value_label)

    @staticmethod
    def _refresh_style(
        widget: QWidget,
    ) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class ResultsPage(QWidget):
    """Display the outcome of an executed audit procedure."""

    back_requested = Signal(str)
    export_requested = Signal(object)

    _PAGE_SIZE = 50

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
        self._presentation: ResultDashboardPresentation | None = None
        self._procedure_breadcrumb_title = "Procedure"

        self._active_filter = "all"
        self._current_page = 1
        self._filtered_rows: tuple[
            DashboardTableRow,
            ...,
        ] = ()

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

        if outcome.result is not None:
            self._presentation = present_result(
                procedure_id=outcome.procedure_id,
                result=outcome.result,
            )
            self._populate_dashboard(self._presentation)
        else:
            self._presentation = None
            self._populate_no_result(outcome)

        self._empty_state.setVisible(False)
        self._result_content.setVisible(True)

    def clear_result(self) -> None:
        """Clear the current result."""

        self._outcome = None
        self._presentation = None
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
        result_layout.addLayout(self._build_analysis_row())
        result_layout.addLayout(self._build_text_panel_row())
        result_layout.addWidget(self._build_exception_section())
        result_layout.addWidget(self._build_evidence_footer())

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
        """Create four reusable headline metric cards."""

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self._metric_cards = tuple(
            ResultMetricCard(
                title="—",
                value="—",
                detail="",
                icon_name="fa5s.circle",
            )
            for _index in range(4)
        )

        for card in self._metric_cards:
            layout.addWidget(
                card,
                1,
            )

        return layout

    def _build_analysis_row(
        self,
    ) -> QHBoxLayout:
        """Build risk-indicator and summary panels."""

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self._risk_panel = QFrame()
        self._risk_panel.setObjectName("resultAnalysisPanel")
        risk_layout = QVBoxLayout(self._risk_panel)
        risk_layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )
        risk_layout.setSpacing(8)

        self._risk_heading = QLabel("Risk Indicators")
        self._risk_heading.setObjectName("resultSectionTitle")

        self._risk_description = QLabel()
        self._risk_description.setObjectName("resultSectionDescription")
        self._risk_description.setWordWrap(True)

        self._risk_items_widget = QWidget()
        self._risk_items_layout = QVBoxLayout(self._risk_items_widget)
        self._risk_items_layout.setContentsMargins(
            0,
            4,
            0,
            0,
        )
        self._risk_items_layout.setSpacing(8)

        risk_layout.addWidget(self._risk_heading)
        risk_layout.addWidget(self._risk_description)
        risk_layout.addWidget(self._risk_items_widget)
        risk_layout.addStretch(1)

        self._summary_panel = QFrame()
        self._summary_panel.setObjectName("resultAnalysisPanel")
        summary_layout = QVBoxLayout(self._summary_panel)
        summary_layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )
        summary_layout.setSpacing(8)

        self._summary_heading = QLabel()
        self._summary_heading.setObjectName("resultSectionTitle")

        self._summary_description = QLabel()
        self._summary_description.setObjectName("resultSectionDescription")
        self._summary_description.setWordWrap(True)

        self._summary_table = QTableWidget()
        self._summary_table.setObjectName("resultExceptionTable")
        self._summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._summary_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._summary_table.verticalHeader().setVisible(False)
        self._summary_table.setMinimumHeight(150)
        self._summary_table.setMaximumHeight(190)

        summary_layout.addWidget(self._summary_heading)
        summary_layout.addWidget(self._summary_description)
        summary_layout.addWidget(self._summary_table)

        layout.addWidget(
            self._risk_panel,
            1,
        )
        layout.addWidget(
            self._summary_panel,
            1,
        )

        return layout

    def _build_text_panel_row(
        self,
    ) -> QHBoxLayout:
        """Build observations and attention panels."""

        layout = QHBoxLayout()
        layout.setSpacing(10)

        (
            self._observations_panel,
            self._observations_layout,
        ) = self._build_text_panel("Key Observations")

        (
            self._attention_panel,
            self._attention_layout,
        ) = self._build_text_panel("Areas Requiring Attention")

        layout.addWidget(
            self._observations_panel,
            1,
        )
        layout.addWidget(
            self._attention_panel,
            1,
        )

        return layout

    def _build_text_panel(
        self,
        title: str,
    ) -> tuple[QFrame, QVBoxLayout]:
        """Create one reusable bullet-text panel."""

        frame = QFrame()
        frame.setObjectName("resultAnalysisPanel")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            20,
            16,
            20,
            16,
        )
        layout.setSpacing(7)

        heading = QLabel(title)
        heading.setObjectName("resultSectionTitle")
        layout.addWidget(heading)

        return frame, layout

    def _build_exception_section(
        self,
    ) -> QFrame:
        """Create the detailed exception explorer."""

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

        heading_row = QHBoxLayout()
        heading_row.setSpacing(8)

        heading_column = QVBoxLayout()
        heading_column.setSpacing(3)

        self._exceptions_heading = QLabel("Detailed Exceptions")
        self._exceptions_heading.setObjectName("resultSectionTitle")

        self._exceptions_description = QLabel(
            "Source-linked records identified by the audit procedure."
        )
        self._exceptions_description.setObjectName("resultSectionDescription")
        self._exceptions_description.setWordWrap(True)

        heading_column.addWidget(self._exceptions_heading)
        heading_column.addWidget(self._exceptions_description)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("formInput")
        self._search_input.setPlaceholderText("Search transactions")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumWidth(230)
        self._search_input.textChanged.connect(self._apply_table_view)

        heading_row.addLayout(
            heading_column,
            1,
        )
        heading_row.addWidget(self._search_input)

        layout.addLayout(heading_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self._filter_button_group = QButtonGroup(self)
        self._filter_button_group.setExclusive(True)
        self._filter_buttons_layout = QHBoxLayout()
        self._filter_buttons_layout.setSpacing(6)

        filter_row.addLayout(self._filter_buttons_layout)
        filter_row.addStretch(1)

        self._filters_button = QToolButton()
        self._filters_button.setObjectName("resultMoreButton")
        self._filters_button.setText("Filters")
        self._filters_button.setIcon(qta.icon("fa5s.filter"))
        self._filters_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._filters_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self._columns_button = QToolButton()
        self._columns_button.setObjectName("resultMoreButton")
        self._columns_button.setText("Columns")
        self._columns_button.setIcon(qta.icon("fa5s.columns"))
        self._columns_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._columns_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        filter_row.addWidget(self._filters_button)
        filter_row.addWidget(self._columns_button)

        layout.addLayout(filter_row)

        self._exceptions_table = QTableWidget()
        self._exceptions_table.setObjectName("resultExceptionTable")
        self._exceptions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._exceptions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._exceptions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._exceptions_table.setAlternatingRowColors(True)
        self._exceptions_table.verticalHeader().setVisible(False)
        self._exceptions_table.setMinimumHeight(300)

        layout.addWidget(self._exceptions_table)

        pagination_row = QHBoxLayout()
        pagination_row.setSpacing(8)

        self._table_count_label = QLabel()
        self._table_count_label.setObjectName("resultSectionDescription")

        self._previous_page_button = QPushButton("Previous")
        self._previous_page_button.setObjectName("secondaryActionButton")
        self._previous_page_button.clicked.connect(self._previous_page)

        self._page_label = QLabel()
        self._page_label.setObjectName("resultMetadataText")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._next_page_button = QPushButton("Next")
        self._next_page_button.setObjectName("secondaryActionButton")
        self._next_page_button.clicked.connect(self._next_page)

        pagination_row.addWidget(self._table_count_label)
        pagination_row.addStretch(1)
        pagination_row.addWidget(self._previous_page_button)
        pagination_row.addWidget(self._page_label)
        pagination_row.addWidget(self._next_page_button)

        layout.addLayout(pagination_row)

        return frame

    def _build_evidence_footer(
        self,
    ) -> QFrame:
        """Create the evidence traceability note."""

        frame = QFrame()
        frame.setObjectName("resultMetadataStrip")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            16,
            10,
            16,
            10,
        )
        layout.setSpacing(10)

        icon = QLabel()
        icon.setPixmap(
            qta.icon(
                "fa5s.link",
                color="#67756A",
            ).pixmap(
                QSize(
                    15,
                    15,
                )
            )
        )

        self._evidence_note = QLabel()
        self._evidence_note.setObjectName("resultMetadataText")
        self._evidence_note.setWordWrap(True)

        evidence_button = QPushButton("View Evidence Details")
        evidence_button.setObjectName("secondaryActionButton")
        evidence_button.setEnabled(False)

        layout.addWidget(icon)
        layout.addWidget(
            self._evidence_note,
            1,
        )
        layout.addWidget(evidence_button)

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
            TestEngineStatus.COMPLETED: "Completed",
            TestEngineStatus.FAILED: "Failed",
            TestEngineStatus.CANCELLED: "Cancelled",
            TestEngineStatus.BLOCKED: "Blocked",
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

    def _populate_dashboard(
        self,
        presentation: ResultDashboardPresentation,
    ) -> None:
        """Render a procedure-neutral dashboard model."""

        for index, card in enumerate(self._metric_cards):
            if index < len(presentation.metrics):
                card.set_content(presentation.metrics[index])
                card.setVisible(True)
            else:
                card.setVisible(False)

        self._populate_risk_panel(presentation)
        self._populate_summary_panel(presentation.summary)
        self._populate_text_panel(
            self._observations_layout,
            presentation.observations,
        )
        self._populate_text_panel(
            self._attention_layout,
            presentation.attention_areas,
        )
        self._populate_exception_table(presentation.table)

        self._evidence_note.setText(presentation.table.source_note)

    def _populate_no_result(
        self,
        outcome: TestEngineOutcome,
    ) -> None:
        """Render a failed or blocked result state."""

        fallback_metrics = (
            DashboardMetric(
                title="Population",
                value="—",
                detail="No result population",
                icon_name="fa5s.database",
            ),
            DashboardMetric(
                title="Evaluated",
                value="—",
                detail="No records evaluated",
                icon_name="fa5s.check-circle",
            ),
            DashboardMetric(
                title="Exceptions",
                value="—",
                detail="No exception result",
                icon_name="fa5s.exclamation-triangle",
            ),
            DashboardMetric(
                title="Exception %",
                value="—",
                detail="No exception rate",
                icon_name="fa5s.percentage",
            ),
        )

        for card, metric in zip(
            self._metric_cards,
            fallback_metrics,
            strict=True,
        ):
            card.set_content(metric)

        self._risk_heading.setText("Audit Analysis")
        self._risk_description.setText(
            outcome.error_message or ("The procedure did not produce a completed result.")
        )
        self._clear_layout(self._risk_items_layout)

        self._summary_panel.setVisible(False)

        self._populate_text_panel(
            self._observations_layout,
            (),
        )
        self._populate_text_panel(
            self._attention_layout,
            (),
        )

        self._exceptions_heading.setText("Detailed Exceptions")
        self._exceptions_description.setText("No completed result is available.")
        self._exceptions_table.clear()
        self._exceptions_table.setRowCount(0)
        self._exceptions_table.setColumnCount(0)
        self._evidence_note.setText("No evidence detail is available for this result.")

    def _populate_risk_panel(
        self,
        presentation: ResultDashboardPresentation,
    ) -> None:
        self._risk_heading.setText(presentation.risk_title)
        self._risk_description.setText(presentation.risk_description)

        self._clear_layout(self._risk_items_layout)

        if not presentation.risk_indicators:
            message = QLabel("No additional risk indicators are defined for this result.")
            message.setObjectName("resultSectionDescription")
            message.setWordWrap(True)
            self._risk_items_layout.addWidget(message)
            return

        for indicator in presentation.risk_indicators:
            self._risk_items_layout.addWidget(self._build_indicator_card(indicator))

    def _build_indicator_card(
        self,
        indicator: DashboardIndicator,
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setProperty(
            "available",
            indicator.available,
        )

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            12,
            9,
            12,
            9,
        )
        layout.setSpacing(10)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        title = QLabel(indicator.title)
        title.setObjectName("cardTitle")

        detail = QLabel(indicator.detail)
        detail.setObjectName("cardText")
        detail.setWordWrap(True)

        value = QLabel(indicator.value)
        value.setObjectName("resultMetricValue")
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        text_layout.addWidget(title)
        text_layout.addWidget(detail)

        layout.addLayout(
            text_layout,
            1,
        )
        layout.addWidget(value)

        return frame

    def _populate_summary_panel(
        self,
        summary: DashboardSummary | None,
    ) -> None:
        if summary is None:
            self._summary_panel.setVisible(False)
            return

        self._summary_panel.setVisible(True)
        self._summary_heading.setText(summary.title)
        self._summary_description.setText(summary.description)

        self._summary_table.clear()
        self._summary_table.setColumnCount(len(summary.headers) + 1)
        self._summary_table.setHorizontalHeaderLabels(
            (
                "",
                *summary.headers,
            )
        )
        self._summary_table.setRowCount(len(summary.rows))

        for row_index, row in enumerate(summary.rows):
            label_item = QTableWidgetItem(row.label)
            self._summary_table.setItem(
                row_index,
                0,
                label_item,
            )

            for value_index, value in enumerate(
                row.values,
                start=1,
            ):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._summary_table.setItem(
                    row_index,
                    value_index,
                    item,
                )

        header = self._summary_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        for column_index in range(
            1,
            self._summary_table.columnCount(),
        ):
            header.setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.Stretch,
            )

    def _populate_text_panel(
        self,
        layout: QVBoxLayout,
        items: tuple[str, ...],
    ) -> None:
        while layout.count() > 1:
            item = layout.takeAt(1)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        if not items:
            label = QLabel("—")
            label.setObjectName("resultSectionDescription")
            layout.addWidget(label)
            return

        for text in items:
            label = QLabel(f"• {text}")
            label.setObjectName("resultSectionDescription")
            label.setWordWrap(True)
            layout.addWidget(label)

    def _populate_exception_table(
        self,
        table: DashboardTable,
    ) -> None:
        self._exceptions_heading.setText(table.title)
        self._exceptions_description.setText(table.description)

        self._active_filter = table.filters[0].key if table.filters else "all"
        self._current_page = 1

        self._rebuild_filter_controls(table)
        self._rebuild_column_menu(table)
        self._search_input.clear()

        self._exceptions_table.clear()
        self._exceptions_table.setColumnCount(len(table.columns))
        self._exceptions_table.setHorizontalHeaderLabels(
            tuple(column.label for column in table.columns)
        )

        header = self._exceptions_table.horizontalHeader()

        for index, column in enumerate(table.columns):
            if column.key in {
                "transaction_description",
                "details",
                "reason",
                "risk_indicators",
            }:
                mode = QHeaderView.ResizeMode.Stretch
            else:
                mode = QHeaderView.ResizeMode.ResizeToContents

            header.setSectionResizeMode(
                index,
                mode,
            )

        self._apply_table_view()

    def _rebuild_filter_controls(
        self,
        table: DashboardTable,
    ) -> None:
        self._clear_layout(self._filter_buttons_layout)

        self._filter_button_group = QButtonGroup(self)
        self._filter_button_group.setExclusive(True)

        filters_menu = QMenu(self)
        filters_group = QActionGroup(filters_menu)
        filters_group.setExclusive(True)

        for index, table_filter in enumerate(table.filters):
            button = QPushButton(table_filter.label)
            button.setObjectName("secondaryActionButton")
            button.setCheckable(True)
            button.setProperty(
                "filter_key",
                table_filter.key,
            )
            button.clicked.connect(self._filter_button_clicked)

            self._filter_button_group.addButton(button)
            self._filter_buttons_layout.addWidget(button)

            action = QAction(
                table_filter.label,
                filters_menu,
            )
            action.setCheckable(True)
            action.setData(table_filter.key)
            action.triggered.connect(self._filter_action_triggered)
            filters_group.addAction(action)
            filters_menu.addAction(action)

            if index == 0:
                button.setChecked(True)
                action.setChecked(True)

        self._filters_button.setMenu(filters_menu)
        self._filters_button.setEnabled(bool(table.filters))

    def _rebuild_column_menu(
        self,
        table: DashboardTable,
    ) -> None:
        columns_menu = QMenu(self)

        for index, column in enumerate(table.columns):
            action = QAction(
                column.label,
                columns_menu,
            )
            action.setCheckable(True)
            action.setChecked(True)
            action.setData(index)
            action.toggled.connect(self._column_visibility_changed)
            columns_menu.addAction(action)

        self._columns_button.setMenu(columns_menu)
        self._columns_button.setEnabled(bool(table.columns))

    def _filter_button_clicked(
        self,
    ) -> None:
        button = self.sender()

        if not isinstance(
            button,
            QPushButton,
        ):
            return

        filter_key = button.property("filter_key")

        if not isinstance(filter_key, str):
            return

        self._set_filter(filter_key)

    def _filter_action_triggered(
        self,
    ) -> None:
        action = self.sender()

        if not isinstance(
            action,
            QAction,
        ):
            return

        filter_key = action.data()

        if isinstance(filter_key, str):
            self._set_filter(filter_key)

    def _set_filter(
        self,
        filter_key: str,
    ) -> None:
        self._active_filter = filter_key
        self._current_page = 1

        for button in self._filter_button_group.buttons():
            button.setChecked(button.property("filter_key") == filter_key)

        menu = self._filters_button.menu()

        if menu is not None:
            for action in menu.actions():
                action.setChecked(action.data() == filter_key)

        self._apply_table_view()

    def _column_visibility_changed(
        self,
        visible: bool,
    ) -> None:
        action = self.sender()

        if not isinstance(
            action,
            QAction,
        ):
            return

        column_index = action.data()

        if not isinstance(
            column_index,
            int,
        ):
            return

        self._exceptions_table.setColumnHidden(
            column_index,
            not visible,
        )

    def _apply_table_view(self) -> None:
        presentation = self._presentation

        if presentation is None:
            return

        table = presentation.table
        search_text = self._search_input.text().strip().casefold()

        filtered_rows = []

        for row in table.rows:
            if self._active_filter != "all" and self._active_filter not in row.groups:
                continue

            if search_text and not any(
                search_text in value.casefold() for value in row.values.values()
            ):
                continue

            filtered_rows.append(row)

        self._filtered_rows = tuple(filtered_rows)

        page_count = max(
            1,
            (len(self._filtered_rows) + self._PAGE_SIZE - 1) // self._PAGE_SIZE,
        )

        self._current_page = min(
            max(
                1,
                self._current_page,
            ),
            page_count,
        )

        start_index = (self._current_page - 1) * self._PAGE_SIZE
        end_index = start_index + (self._PAGE_SIZE)

        visible_rows = self._filtered_rows[start_index:end_index]

        self._exceptions_table.setRowCount(len(visible_rows))

        for row_index, row in enumerate(visible_rows):
            for column_index, column in enumerate(table.columns):
                value = row.values.get(
                    column.key,
                    "—",
                )

                item = QTableWidgetItem(value)

                if column.key in {
                    "source_row",
                    "debit_amount",
                    "credit_amount",
                    "transaction_amount",
                }:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )

                record_id = row.values.get(
                    "record_id",
                    "",
                )

                if record_id:
                    item.setToolTip(f"Source record: {record_id}")

                self._exceptions_table.setItem(
                    row_index,
                    column_index,
                    item,
                )

        total_matches = len(self._filtered_rows)
        total_rows = len(table.rows)

        self._table_count_label.setText(f"{total_matches:,} of {total_rows:,} transactions")
        self._page_label.setText(f"Page {self._current_page} of {page_count}")

        self._previous_page_button.setEnabled(self._current_page > 1)
        self._next_page_button.setEnabled(self._current_page < page_count)

    def _previous_page(self) -> None:
        if self._current_page <= 1:
            return

        self._current_page -= 1
        self._apply_table_view()

    def _next_page(self) -> None:
        page_count = max(
            1,
            (len(self._filtered_rows) + self._PAGE_SIZE - 1) // self._PAGE_SIZE,
        )

        if self._current_page >= page_count:
            return

        self._current_page += 1
        self._apply_table_view()

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
    def _clear_layout(
        layout: QHBoxLayout | QVBoxLayout,
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

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
                parsed_value = datetime.fromisoformat(
                    value.strip().replace(
                        "Z",
                        "+00:00",
                    )
                )
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
