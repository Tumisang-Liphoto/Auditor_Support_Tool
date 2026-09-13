"""Small keyboard-accessible selector for auditor-facing report formats."""

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QRadioButton, QVBoxLayout


class ReportExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Report")
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Format"))
        self._formats = {}
        for key, label in (("pdf", "PDF"), ("docx", "Word (.docx)"), ("xlsx", "Excel (.xlsx)")):
            radio = QRadioButton(label)
            self._formats[key] = radio
            layout.addWidget(radio)
        self._formats["pdf"].setChecked(True)
        self._formats["pdf"].setFocus()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        export = buttons.addButton("Export", QDialogButtonBox.ButtonRole.AcceptRole)
        export.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def format(self) -> str:
        return next(key for key, button in self._formats.items() if button.isChecked())
