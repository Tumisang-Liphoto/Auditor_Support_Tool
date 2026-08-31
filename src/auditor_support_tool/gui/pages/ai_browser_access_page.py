"""Settings page for secure OpenWebUI browser and API access."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.gui.workers.openwebui_connection_worker import (
    OpenWebUIConnectionWorker,
)
from auditor_support_tool.services.openwebui_client import (
    OpenWebUIClient,
    OpenWebUIConnectionResult,
)
from auditor_support_tool.services.openwebui_settings_service import (
    OpenWebUISettings,
    OpenWebUISettingsService,
    normalize_openwebui_url,
)
from auditor_support_tool.services.windows_credential_service import (
    CredentialStoreError,
    WindowsCredentialService,
)


class AIBrowserAccessPage(QWidget):
    """Configure persistent per-user access to the approved OpenWebUI."""

    def __init__(
        self,
        *,
        settings_file: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings_service = OpenWebUISettingsService(
            settings_file=settings_file,
            credential_store=WindowsCredentialService(),
        )
        self._client = OpenWebUIClient()
        self._worker: OpenWebUIConnectionWorker | None = None

        self._build_interface()
        self._load_settings()

    def _build_interface(
        self,
    ) -> None:
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

        title = QLabel("AI Browser Access")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Configure access to the approved OpenWebUI service. "
            "Your API key is stored securely in Windows Credential Manager "
            "and is not written to the application settings file."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._build_configuration_card())
        layout.addWidget(self._build_status_card())
        layout.addWidget(self._build_guidance_card())
        layout.addStretch(1)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_configuration_card(
        self,
    ) -> QFrame:
        card = self._create_card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            30,
            24,
            30,
            24,
        )
        layout.setSpacing(14)

        heading = QLabel("OpenWebUI Connection")
        heading.setObjectName("profileSectionTitle")

        description = QLabel(
            "The address and enable/disable preference are stored locally. "
            "The API key remains in the Windows credential vault for the "
            "current Windows user."
        )
        description.setObjectName("profileSectionDescription")
        description.setWordWrap(True)

        self._enabled_input = QCheckBox("Enable OpenWebUI integration")

        form = QGridLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)
        form.setColumnMinimumWidth(
            0,
            150,
        )
        form.setColumnStretch(
            1,
            1,
        )

        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("Example: http://server-name:3000")
        self._base_url_input.setClearButtonEnabled(True)

        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("Leave blank to keep the currently saved API key")

        form.addWidget(
            self._field_label("OpenWebUI address"),
            0,
            0,
        )
        form.addWidget(
            self._base_url_input,
            0,
            1,
        )
        form.addWidget(
            self._field_label("API key"),
            1,
            0,
        )
        form.addWidget(
            self._api_key_input,
            1,
            1,
        )

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self._save_button = QPushButton("Save Settings")
        self._save_button.setObjectName("primaryActionButton")
        self._save_button.clicked.connect(self._save_settings)

        self._test_button = QPushButton("Test Connection")
        self._test_button.setObjectName("secondaryActionButton")
        self._test_button.clicked.connect(self._test_connection)

        self._open_button = QPushButton("Open OpenWebUI")
        self._open_button.setObjectName("secondaryActionButton")
        self._open_button.clicked.connect(self._open_openwebui)

        self._remove_key_button = QPushButton("Remove Saved API Key")
        self._remove_key_button.setObjectName("secondaryActionButton")
        self._remove_key_button.clicked.connect(self._remove_saved_key)

        actions.addWidget(self._save_button)
        actions.addWidget(self._test_button)
        actions.addWidget(self._open_button)
        actions.addStretch(1)
        actions.addWidget(self._remove_key_button)

        layout.addWidget(heading)
        layout.addWidget(description)
        layout.addWidget(self._enabled_input)
        layout.addLayout(form)
        layout.addLayout(actions)

        return card

    def _build_status_card(
        self,
    ) -> QFrame:
        card = self._create_card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            30,
            24,
            30,
            24,
        )
        layout.setSpacing(10)

        heading = QLabel("Connection Status")
        heading.setObjectName("profileSectionTitle")

        self._credential_status = QLabel()
        self._credential_status.setObjectName("profileSectionDescription")
        self._credential_status.setWordWrap(True)

        self._connection_status = QLabel("Connection not tested in this session.")
        self._connection_status.setObjectName("formStatus")
        self._connection_status.setProperty(
            "status",
            "neutral",
        )
        self._connection_status.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(self._credential_status)
        layout.addWidget(self._connection_status)

        return card

    def _build_guidance_card(
        self,
    ) -> QFrame:
        card = self._create_card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            30,
            24,
            30,
            24,
        )
        layout.setSpacing(10)

        heading = QLabel("Access and Audit Guidance")
        heading.setObjectName("profileSectionTitle")

        guidance = QLabel(
            "Use an API key created from your own approved OpenWebUI account. "
            "The API key acts with that account's OpenWebUI permissions. "
            "Opening OpenWebUI launches the configured service in your default "
            "browser; browser login is managed by OpenWebUI itself.\n\n"
            "AI output is advisory. Auditors remain responsible for reviewing "
            "evidence, corroborating explanations and exercising professional "
            "judgement before reaching an audit conclusion."
        )
        guidance.setObjectName("profileSectionDescription")
        guidance.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(guidance)

        return card

    def _load_settings(
        self,
    ) -> None:
        settings = self._settings_service.get_settings()

        self._enabled_input.setChecked(settings.enabled)
        self._base_url_input.setText(settings.base_url)
        self._api_key_input.clear()

        self._refresh_credential_status()

    def _save_settings(
        self,
    ) -> None:
        try:
            saved = self._settings_service.save_settings(
                OpenWebUISettings(
                    enabled=self._enabled_input.isChecked(),
                    base_url=self._base_url_input.text(),
                )
            )

            typed_key = self._api_key_input.text().strip()

            if typed_key:
                self._settings_service.save_api_key(
                    base_url=saved.base_url,
                    api_key=typed_key,
                )

            self._base_url_input.setText(saved.base_url)
            self._api_key_input.clear()
        except (
            ValueError,
            CredentialStoreError,
        ) as error:
            QMessageBox.warning(
                self,
                "OpenWebUI Settings",
                str(error),
            )
            return

        self._set_connection_status(
            "OpenWebUI settings saved.",
            "success",
        )
        self._refresh_credential_status()

    def _test_connection(
        self,
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        try:
            base_url = normalize_openwebui_url(self._base_url_input.text())
            api_key = (
                self._api_key_input.text().strip()
                or self._settings_service.get_api_key(base_url)
                or ""
            )
        except (
            ValueError,
            CredentialStoreError,
        ) as error:
            self._set_connection_status(
                str(error),
                "error",
            )
            return

        self._set_testing_state(True)
        self._set_connection_status(
            "Testing authenticated OpenWebUI access…",
            "checking",
        )

        self._worker = OpenWebUIConnectionWorker(
            client=self._client,
            base_url=base_url,
            api_key=api_key,
        )
        self._worker.completed.connect(self._handle_connection_result)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.start()

    def _handle_connection_result(
        self,
        result: OpenWebUIConnectionResult,
    ) -> None:
        self._set_connection_status(
            result.message,
            "success" if result.success else "error",
        )

    def _handle_worker_finished(
        self,
    ) -> None:
        self._set_testing_state(False)

        worker = self._worker
        self._worker = None

        if worker is not None:
            worker.deleteLater()

    def _open_openwebui(
        self,
    ) -> None:
        try:
            base_url = normalize_openwebui_url(self._base_url_input.text())
        except ValueError as error:
            QMessageBox.warning(
                self,
                "OpenWebUI Address",
                str(error),
            )
            return

        opened = QDesktopServices.openUrl(QUrl(base_url))

        if not opened:
            QMessageBox.warning(
                self,
                "OpenWebUI",
                "Windows could not open the configured OpenWebUI address.",
            )

    def _remove_saved_key(
        self,
    ) -> None:
        try:
            base_url = normalize_openwebui_url(self._base_url_input.text())
        except ValueError as error:
            QMessageBox.warning(
                self,
                "Remove API Key",
                str(error),
            )
            return

        answer = QMessageBox.question(
            self,
            "Remove Saved API Key",
            ("Remove the OpenWebUI API key stored in Windows Credential Manager for this address?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self._settings_service.delete_api_key(base_url)
        except CredentialStoreError as error:
            QMessageBox.warning(
                self,
                "Remove API Key",
                str(error),
            )
            return

        self._api_key_input.clear()
        self._refresh_credential_status()
        self._set_connection_status(
            "Saved OpenWebUI API key removed.",
            "neutral",
        )

    def _refresh_credential_status(
        self,
    ) -> None:
        base_url = self._base_url_input.text().strip()

        if not base_url:
            self._credential_status.setText("API credential: no OpenWebUI address configured.")
            self._remove_key_button.setEnabled(False)
            return

        try:
            has_key = self._settings_service.has_api_key(base_url)
        except (
            ValueError,
            CredentialStoreError,
        ):
            has_key = False

        if has_key:
            text = "API credential: securely stored in Windows Credential Manager."
        else:
            text = "API credential: no saved API key for the current OpenWebUI address."

        self._credential_status.setText(text)
        self._remove_key_button.setEnabled(has_key)

    def _set_testing_state(
        self,
        testing: bool,
    ) -> None:
        self._test_button.setEnabled(not testing)
        self._save_button.setEnabled(not testing)

        if testing:
            self._remove_key_button.setEnabled(False)
        else:
            self._refresh_credential_status()

    def _set_connection_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._connection_status.setText(message)
        self._connection_status.setProperty(
            "status",
            status,
        )

        self._connection_status.style().unpolish(self._connection_status)
        self._connection_status.style().polish(self._connection_status)

    @staticmethod
    def _field_label(
        text: str,
    ) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldHint")

        return label

    @staticmethod
    def _create_card() -> QFrame:
        card = QFrame()
        card.setObjectName("profileSectionCard")

        return card
