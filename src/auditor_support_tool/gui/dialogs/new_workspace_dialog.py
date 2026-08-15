"""Dialog for creating a new audit workspace."""

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.workspace_models import WorkspaceIdentity


class NewWorkspaceDialog(QDialog):
    """Collect identity information for a new audit workspace."""

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_identity: WorkspaceIdentity | None = None

        self.setWindowTitle("New Audit Workspace")
        self.setModal(True)
        self.setMinimumWidth(540)

        self._build_interface()

    @property
    def workspace_identity(self) -> WorkspaceIdentity | None:
        """Return the identity created after successful validation."""

        return self._workspace_identity

    def _build_interface(self) -> None:
        """Build the workspace form."""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        title = QLabel("Create a New Audit Workspace")
        title.setObjectName("dialogTitle")

        description = QLabel(
            "Enter the basic information for the audit workspace. "
            "The workspace can be saved after it has been created."
        )
        description.setObjectName("dialogDescription")
        description.setWordWrap(True)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(18)
        form_layout.setVerticalSpacing(12)

        self._workspace_name_input = QLineEdit()
        self._workspace_name_input.setPlaceholderText("Example: 2026 Payroll Audit")
        self._workspace_name_input.setClearButtonEnabled(True)

        self._auditee_name_input = QLineEdit()
        self._auditee_name_input.setPlaceholderText("Example: Ministry of Example")
        self._auditee_name_input.setClearButtonEnabled(True)

        today = QDate.currentDate()

        self._audit_year_input = QComboBox()
        self._audit_year_input.setObjectName("modernYearSelector")
        self._audit_year_input.setMinimumHeight(38)

        current_year = today.year()

        for year in range(
            current_year + 5,
            current_year - 11,
            -1,
        ):
            self._audit_year_input.addItem(
                str(year),
                year,
            )

        current_year_index = self._audit_year_input.findData(current_year)

        if current_year_index >= 0:
            self._audit_year_input.setCurrentIndex(current_year_index)

        self._audit_year_input.setToolTip("Select the audit year.")

        self._audit_period_start_input = QDateEdit()
        self._configure_date_picker(
            self._audit_period_start_input,
            today,
            "Select the first day of the audit period.",
        )

        self._audit_period_end_input = QDateEdit()
        self._configure_date_picker(
            self._audit_period_end_input,
            today,
            "Select the last day of the audit period.",
        )

        self._audit_domain_combo = QComboBox()
        self._audit_domain_combo.addItem(
            "Select audit domain",
            "",
        )
        self._audit_domain_combo.addItem(
            "Financial Audit",
            "Financial Audit",
        )
        self._audit_domain_combo.addItem(
            "Compliance Audit",
            "Compliance Audit",
        )
        self._audit_domain_combo.addItem(
            "Performance Audit",
            "Performance Audit",
        )
        self._audit_domain_combo.addItem(
            "Information Technology Audit",
            "Information Technology Audit",
        )
        self._audit_domain_combo.addItem(
            "Other",
            "Other",
        )

        self._audit_area_input = QLineEdit()
        self._audit_area_input.setPlaceholderText("Example: Payroll, General Ledger or ITGC")
        self._audit_area_input.setClearButtonEnabled(True)

        self._lead_auditor_input = QLineEdit()
        self._lead_auditor_input.setPlaceholderText("Name of the responsible auditor")
        self._lead_auditor_input.setClearButtonEnabled(True)

        self._description_input = QPlainTextEdit()
        self._description_input.setPlaceholderText(
            "Optional notes about the purpose or scope of the workspace."
        )
        self._description_input.setMaximumHeight(110)

        form_layout.addRow(
            "Workspace name:",
            self._workspace_name_input,
        )
        form_layout.addRow(
            "Auditee name:",
            self._auditee_name_input,
        )
        form_layout.addRow(
            "Audit year:",
            self._audit_year_input,
        )
        form_layout.addRow(
            "Period start:",
            self._audit_period_start_input,
        )
        form_layout.addRow(
            "Period end:",
            self._audit_period_end_input,
        )
        form_layout.addRow(
            "Audit domain:",
            self._audit_domain_combo,
        )
        form_layout.addRow(
            "Audit area:",
            self._audit_area_input,
        )
        form_layout.addRow(
            "Lead auditor:",
            self._lead_auditor_input,
        )
        form_layout.addRow(
            "Description:",
            self._description_input,
        )

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )

        create_button = self._button_box.button(QDialogButtonBox.StandardButton.Ok)

        if create_button is not None:
            create_button.setText("Create Workspace")
            create_button.setDefault(True)

        self._button_box.accepted.connect(self._accept_workspace)
        self._button_box.rejected.connect(self.reject)

        root_layout.addWidget(title)
        root_layout.addWidget(description)
        root_layout.addLayout(form_layout)
        root_layout.addWidget(self._button_box)

        self._apply_modern_field_style()

        self._workspace_name_input.setFocus()

    @staticmethod
    def _configure_date_picker(
        date_input: QDateEdit,
        date: QDate,
        tooltip: str,
    ) -> None:
        """Configure a modern calendar-backed date selector."""

        date_input.setObjectName("modernDatePicker")
        date_input.setCalendarPopup(True)
        date_input.setDisplayFormat("dd MMM yyyy")
        date_input.setDate(date)
        date_input.setMinimumHeight(38)
        date_input.setToolTip(tooltip)

    def _apply_modern_field_style(self) -> None:
        """Apply modern styling to year and date selectors."""

        self.setStyleSheet(
            self.styleSheet()
            + """
            QComboBox#modernYearSelector,
            QDateEdit#modernDatePicker {
                min-height: 38px;
                padding-left: 12px;
                padding-right: 8px;
                border: 1px solid #C9CED6;
                border-radius: 7px;
                background-color: #FFFFFF;
            }

            QComboBox#modernYearSelector:hover,
            QDateEdit#modernDatePicker:hover {
                border-color: #8A94A3;
            }

            QComboBox#modernYearSelector:focus,
            QDateEdit#modernDatePicker:focus {
                border: 1px solid #4A7BD0;
            }

            QComboBox#modernYearSelector::drop-down,
            QDateEdit#modernDatePicker::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 34px;
                border: none;
                border-left: 1px solid #E3E6EA;
            }

            QComboBox#modernYearSelector QAbstractItemView {
                padding: 4px;
                selection-background-color: #E8EEF8;
                selection-color: #202124;
            }
            """
        )

    def _accept_workspace(self) -> None:
        """Validate the form and create the workspace identity."""

        workspace_name = self._workspace_name_input.text().strip()

        if not workspace_name:
            QMessageBox.warning(
                self,
                "Workspace Name Required",
                "Enter a name for the audit workspace.",
            )
            self._workspace_name_input.setFocus()
            return

        audit_period_start = self._audit_period_start_input.date().toString(Qt.DateFormat.ISODate)

        audit_period_end = self._audit_period_end_input.date().toString(Qt.DateFormat.ISODate)

        try:
            self._workspace_identity = WorkspaceIdentity.create(
                name=workspace_name,
                auditee_name=(self._auditee_name_input.text()),
                audit_year=str(self._audit_year_input.currentData()),
                audit_period_start=(audit_period_start),
                audit_period_end=(audit_period_end),
                audit_domain=str(self._audit_domain_combo.currentData() or ""),
                audit_area=(self._audit_area_input.text()),
                lead_auditor=(self._lead_auditor_input.text()),
                description=(self._description_input.toPlainText()),
            )
        except ValueError as error:
            QMessageBox.warning(
                self,
                "Invalid Workspace",
                str(error),
            )
            return

        self.accept()
