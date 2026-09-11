"""Dialog for unlocking administrator-protected settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.services.administrator_settings_service import (
    AdministratorSettingsService,
)


class AdministratorUnlockDialog(QDialog):
    """Prompt an authorised technician for the shared settings password."""

    def __init__(
        self,
        *,
        administrator_settings_service: AdministratorSettingsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._administrator_settings_service = administrator_settings_service

        self.setWindowTitle("Administrator Access")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        description = QLabel(
            "Enter the shared technician password to change protected application settings."
        )
        description.setWordWrap(True)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("Technician password")
        self._password_input.returnPressed.connect(self._attempt_unlock)

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.setObjectName("formStatus")
        self._status_label.setProperty("status", "error")
        self._status_label.hide()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        unlock_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        unlock_button.setText("Unlock")
        buttons.accepted.connect(self._attempt_unlock)
        buttons.rejected.connect(self.reject)

        layout.addWidget(description)
        layout.addWidget(self._password_input)
        layout.addWidget(self._status_label)
        layout.addWidget(buttons)

        if not self._administrator_settings_service.is_configured:
            self._status_label.setText(
                "The technician password is not configured for this application build."
            )
            self._status_label.show()
            self._password_input.setEnabled(False)
            unlock_button.setEnabled(False)

    def _attempt_unlock(self) -> None:
        result = self._administrator_settings_service.unlock(self._password_input.text())
        if result.success:
            self.accept()
            return

        self._status_label.setText(result.message)
        self._status_label.show()
        self._password_input.clear()
        self._password_input.setFocus()
