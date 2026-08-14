"""Dialog for creating a new audit workspace."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
        self.setMinimumWidth(520)

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

        self._audit_year_input = QLineEdit()
        self._audit_year_input.setPlaceholderText("Example: 2026")
        self._audit_year_input.setMaxLength(20)
        self._audit_year_input.setClearButtonEnabled(True)

        self._audit_period_start_input = QLineEdit()
        self._audit_period_start_input.setPlaceholderText("YYYY-MM-DD, example: 2026-04-01")
        self._audit_period_start_input.setMaxLength(10)
        self._audit_period_start_input.setClearButtonEnabled(True)

        self._audit_period_end_input = QLineEdit()
        self._audit_period_end_input.setPlaceholderText("YYYY-MM-DD, example: 2027-03-31")
        self._audit_period_end_input.setMaxLength(10)
        self._audit_period_end_input.setClearButtonEnabled(True)

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

        self._workspace_name_input.setFocus()

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

        try:
            self._workspace_identity = WorkspaceIdentity.create(
                name=workspace_name,
                auditee_name=self._auditee_name_input.text(),
                audit_year=self._audit_year_input.text(),
                audit_period_start=(self._audit_period_start_input.text()),
                audit_period_end=(self._audit_period_end_input.text()),
                audit_domain=str(self._audit_domain_combo.currentData() or ""),
                audit_area=self._audit_area_input.text(),
                lead_auditor=self._lead_auditor_input.text(),
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
