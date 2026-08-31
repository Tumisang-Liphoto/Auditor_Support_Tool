"""In-application human-readable audit procedure report dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.audit_procedure_report_models import (
    AuditProcedureReport,
)
from auditor_support_tool.presentation.audit_procedure_report_formatter import (
    build_exception_columns,
    exception_cell_value,
    report_display_label,
    report_display_value,
)


class AuditProcedureReportDialog(QDialog):
    """Display one complete structured audit procedure report."""

    def __init__(
        self,
        *,
        report: AuditProcedureReport,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._report = report

        self.setWindowTitle(f"{report.identity.display_id} Audit Procedure Report")
        self.setModal(True)
        self.resize(
            1180,
            780,
        )
        self.setMinimumSize(
            900,
            620,
        )

        self._build_interface()

    @property
    def report(self) -> AuditProcedureReport:
        """Return the structured report displayed by the dialog."""

        return self._report

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("pageContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            34,
            26,
            34,
            28,
        )
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addLayout(self._build_heading())
        layout.addWidget(self._build_scope_card())
        layout.addWidget(self._build_summary_card())
        layout.addWidget(self._build_analysis_card())
        layout.addWidget(self._build_limitations_card())
        layout.addWidget(self._build_exception_card())
        layout.addWidget(self._build_reproducibility_card())

        scroll_area.setWidget(content)
        root_layout.addWidget(
            scroll_area,
            1,
        )

        footer = QFrame()
        footer.setObjectName("profileSectionCard")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(
            18,
            10,
            18,
            10,
        )

        fingerprint = QLabel(f"Report fingerprint: {self._report.report_fingerprint}")
        fingerprint.setObjectName("fieldHint")
        fingerprint.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        close_button = QPushButton("Close")
        close_button.setObjectName("secondaryActionButton")
        close_button.clicked.connect(self.accept)

        footer_layout.addWidget(
            fingerprint,
            1,
        )
        footer_layout.addWidget(close_button)

        root_layout.addWidget(footer)

    def _build_heading(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title = QLabel(f"{self._report.identity.display_id} — {self._report.identity.name}")
        title.setObjectName("pageTitle")
        title.setWordWrap(True)

        subtitle = QLabel("Audit Procedure Report")
        subtitle.setObjectName("pageSubtitle")

        description = QLabel(
            self._report.identity.description or "Completed audit procedure report."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        text_layout.addWidget(description)

        layout.addLayout(
            text_layout,
            1,
        )

        return layout

    def _build_scope_card(self) -> QFrame:
        card, layout = self._card(
            "Scope and Procedure",
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(8)

        rows = (
            (
                "Procedure",
                (f"{self._report.identity.display_id} — {self._report.identity.name}"),
            ),
            (
                "Category",
                self._report.identity.category,
            ),
            (
                "Procedure version",
                self._report.identity.procedure_version,
            ),
            (
                "Dataset ID",
                self._report.scope.dataset_id,
            ),
            (
                "Audit period",
                self._audit_period_text(),
            ),
        )

        for row, (
            label,
            value,
        ) in enumerate(rows):
            self._add_grid_row(
                grid,
                row,
                label,
                value,
            )

        if self._report.scope.parameters:
            parameter_text = "; ".join(
                f"{report_display_label(key)}: {report_display_value(value)}"
                for key, value in self._report.scope.parameters.items()
            )
        else:
            parameter_text = "No procedure parameters recorded."

        self._add_grid_row(
            grid,
            len(rows),
            "Parameters",
            parameter_text,
        )

        layout.addLayout(grid)

        return card

    def _build_summary_card(self) -> QFrame:
        card, layout = self._card(
            "Result Summary",
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(8)

        summary = self._report.summary

        rows = (
            (
                "Population",
                f"{summary.population_count:,}",
            ),
            (
                "Records evaluated",
                f"{summary.records_evaluated_count:,}",
            ),
            (
                "Records excluded",
                f"{summary.excluded_record_count:,}",
            ),
            (
                "Exceptions",
                f"{summary.exception_count:,}",
            ),
            (
                "Exception rate",
                f"{summary.exception_rate:.2f}%",
            ),
            (
                "Related value total",
                summary.related_value_total or "Not reported",
            ),
        )

        for row, (
            label,
            value,
        ) in enumerate(rows):
            self._add_grid_row(
                grid,
                row,
                label,
                value,
            )

        layout.addLayout(grid)

        if self._report.exclusion_counts:
            exclusion_text = "; ".join(
                f"{report_display_label(key)}: {value:,}"
                for key, value in self._report.exclusion_counts.items()
            )

            exclusion_label = QLabel(f"Exclusions — {exclusion_text}")
            exclusion_label.setObjectName("profileSectionDescription")
            exclusion_label.setWordWrap(True)

            layout.addWidget(exclusion_label)

        return card

    def _build_analysis_card(self) -> QFrame:
        card, layout = self._card(
            "Analysis",
        )

        if self._report.metrics:
            metrics_table = QTableWidget()
            metrics_table.setObjectName("auditReportMetricsTable")
            metrics_table.setColumnCount(2)
            metrics_table.setHorizontalHeaderLabels(
                (
                    "Metric",
                    "Value",
                )
            )
            metrics_table.setRowCount(len(self._report.metrics))
            metrics_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            metrics_table.verticalHeader().setVisible(False)
            metrics_table.setAlternatingRowColors(True)

            for row, (
                key,
                value,
            ) in enumerate(self._report.metrics.items()):
                metrics_table.setItem(
                    row,
                    0,
                    QTableWidgetItem(report_display_label(key)),
                )
                metrics_table.setItem(
                    row,
                    1,
                    QTableWidgetItem(report_display_value(value)),
                )

            header = metrics_table.horizontalHeader()
            header.setSectionResizeMode(
                0,
                QHeaderView.ResizeMode.ResizeToContents,
            )
            header.setSectionResizeMode(
                1,
                QHeaderView.ResizeMode.Stretch,
            )

            metrics_table.setMinimumHeight(
                min(
                    320,
                    max(
                        130,
                        36 * len(self._report.metrics) + 50,
                    ),
                )
            )

            layout.addWidget(metrics_table)
        else:
            layout.addWidget(self._message_label("No additional procedure metrics were recorded."))

        for section in self._report.analysis_sections:
            heading = QLabel(section.title)
            heading.setObjectName("resultSectionTitle")

            layout.addWidget(heading)

            if section.narrative:
                layout.addWidget(self._message_label(section.narrative))

            if section.data:
                data_text = "; ".join(
                    f"{report_display_label(key)}: {report_display_value(value)}"
                    for key, value in section.data.items()
                )
                layout.addWidget(self._message_label(data_text))

        return card

    def _build_limitations_card(self) -> QFrame:
        card, layout = self._card(
            "Interpretation and Limitations",
        )

        statement_heading = QLabel("Audit use statement")
        statement_heading.setObjectName("resultSectionTitle")

        layout.addWidget(statement_heading)
        layout.addWidget(self._message_label(self._report.audit_use_statement))

        limitation_heading = QLabel("Recorded limitations")
        limitation_heading.setObjectName("resultSectionTitle")

        layout.addWidget(limitation_heading)

        if self._report.limitations:
            for limitation in self._report.limitations:
                layout.addWidget(self._message_label(f"• {limitation}"))
        else:
            layout.addWidget(
                self._message_label("No additional execution limitations were recorded.")
            )

        return card

    def _build_exception_card(self) -> QFrame:
        card, layout = self._card(
            (f"Exception Detail ({self._report.summary.exception_count:,})"),
        )

        description = QLabel(
            "Complete source-linked records identified by the procedure are shown below."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        layout.addWidget(description)

        exceptions = self._report.exceptions
        columns = build_exception_columns(exceptions)

        table = QTableWidget()
        table.setObjectName("auditReportExceptionTable")
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(tuple(column.label for column in columns))
        table.setRowCount(len(exceptions))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        for row, exception in enumerate(exceptions):
            for column_index, column in enumerate(columns):
                table.setItem(
                    row,
                    column_index,
                    QTableWidgetItem(
                        exception_cell_value(
                            exception,
                            column.key,
                        )
                    ),
                )

        header = table.horizontalHeader()

        for column_index in range(len(columns)):
            header.setSectionResizeMode(
                column_index,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        if len(columns) > 1:
            header.setSectionResizeMode(
                1,
                QHeaderView.ResizeMode.Stretch,
            )

        table.setMinimumHeight(
            min(
                430,
                max(
                    180,
                    30 * len(exceptions) + 55,
                ),
            )
        )

        layout.addWidget(table)

        return card

    def _build_reproducibility_card(self) -> QFrame:
        card, layout = self._card(
            "Reproducibility",
        )

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(8)

        rows = (
            (
                "Execution ID",
                self._report.execution_id,
            ),
            (
                "Created",
                self._report.created_at,
            ),
            (
                "Source SHA-256",
                self._report.source_sha256,
            ),
            (
                "Mapping fingerprint",
                self._report.mapping_fingerprint,
            ),
            (
                "Report fingerprint",
                self._report.report_fingerprint,
            ),
        )

        for row, (
            label,
            value,
        ) in enumerate(rows):
            self._add_grid_row(
                grid,
                row,
                label,
                value,
            )

        layout.addLayout(grid)

        return card

    @staticmethod
    def _card(
        title: str,
    ) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("profileSectionCard")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            24,
            20,
            24,
            20,
        )
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("profileSectionTitle")

        layout.addWidget(heading)

        return (
            card,
            layout,
        )

    @staticmethod
    def _add_grid_row(
        grid: QGridLayout,
        row: int,
        label: str,
        value: str,
    ) -> None:
        label_widget = QLabel(label)
        label_widget.setObjectName("fieldHint")

        value_widget = QLabel(value or "—")
        value_widget.setObjectName("profileSectionDescription")
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        grid.addWidget(
            label_widget,
            row,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        grid.addWidget(
            value_widget,
            row,
            1,
        )

    @staticmethod
    def _message_label(
        text: str,
    ) -> QLabel:
        label = QLabel(text)
        label.setObjectName("profileSectionDescription")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        return label

    def _audit_period_text(self) -> str:
        start = self._report.scope.audit_period_start.strip()
        end = self._report.scope.audit_period_end.strip()

        if not start and not end:
            return "Not specified"

        if start and end:
            return f"{start} to {end}"

        return start or end
