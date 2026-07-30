"""Local user-profile setup and maintenance page."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.services.settings_service import (
    SettingsService,
    UserProfile,
)


class UserProfilePage(QWidget):
    """Page used to configure the local auditor profile."""

    profile_saved = Signal(object)

    def __init__(
        self,
        settings_service: SettingsService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings_service = settings_service

        self._display_name_input = QLineEdit()
        self._organization_input = QLineEdit()
        self._role_input = QLineEdit()
        self._currency_input = QComboBox()
        self._status_label = QLabel()

        self._build_interface()
        self.load_profile()

    def _build_interface(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel("User Profile")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Configure the local auditor information used when creating "
            "engagements and generating reports."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        profile_card = QFrame()
        profile_card.setObjectName("card")
        profile_card.setMaximumWidth(720)

        card_layout = QVBoxLayout(profile_card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(16)

        card_title = QLabel("Auditor Information")
        card_title.setObjectName("cardTitle")

        required_note = QLabel(
            "Display name and organisation are required. "
            "The information is stored only on this computer."
        )
        required_note.setObjectName("cardText")
        required_note.setWordWrap(True)

        self._display_name_input.setObjectName("formInput")
        self._display_name_input.setPlaceholderText("For example: Tumisang Liphoto")
        self._display_name_input.setClearButtonEnabled(True)

        self._organization_input.setObjectName("formInput")
        self._organization_input.setPlaceholderText("For example: Office of the Auditor-General")
        self._organization_input.setClearButtonEnabled(True)

        self._role_input.setObjectName("formInput")
        self._role_input.setPlaceholderText("For example: Auditor")
        self._role_input.setClearButtonEnabled(True)

        self._currency_input.setObjectName("formInput")
        self._currency_input.setEditable(True)
        self._currency_input.addItems(
            [
                "LSL",
                "ZAR",
                "USD",
                "EUR",
                "GBP",
            ]
        )

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(22)
        form_layout.setVerticalSpacing(14)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        form_layout.addRow(
            "Display name *",
            self._display_name_input,
        )
        form_layout.addRow(
            "Organisation *",
            self._organization_input,
        )
        form_layout.addRow(
            "Role",
            self._role_input,
        )
        form_layout.addRow(
            "Default currency",
            self._currency_input,
        )

        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        save_button = QPushButton("Save Profile")
        save_button.setObjectName("primaryActionButton")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.clicked.connect(self.save_profile)

        card_layout.addWidget(card_title)
        card_layout.addWidget(required_note)
        card_layout.addLayout(form_layout)
        card_layout.addWidget(self._status_label)
        card_layout.addWidget(
            save_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(
            profile_card,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addStretch()

    def load_profile(self) -> None:
        """Load the saved profile into the form."""

        profile = self._settings_service.get_user_profile()

        self._display_name_input.setText(profile.display_name)
        self._organization_input.setText(profile.organization)
        self._role_input.setText(profile.role)

        currency_index = self._currency_input.findText(
            profile.default_currency,
            Qt.MatchFlag.MatchFixedString,
        )

        if currency_index >= 0:
            self._currency_input.setCurrentIndex(currency_index)
        else:
            self._currency_input.setCurrentText(profile.default_currency)

    def save_profile(self) -> None:
        """Validate and save the local profile."""

        display_name = self._display_name_input.text().strip()
        organization = self._organization_input.text().strip()
        role = self._role_input.text().strip() or "Auditor"
        currency = self._currency_input.currentText().strip().upper() or "LSL"

        if not display_name:
            self._show_error("Enter the auditor's display name.")
            self._display_name_input.setFocus()
            return

        if not organization:
            self._show_error("Enter the auditor's organisation.")
            self._organization_input.setFocus()
            return

        if len(currency) != 3 or not currency.isalpha():
            self._show_error("Enter a valid three-letter currency code.")
            self._currency_input.setFocus()
            return

        profile = UserProfile(
            display_name=display_name,
            organization=organization,
            role=role,
            default_currency=currency,
        )

        self._settings_service.save_user_profile(profile)

        self._show_success("User profile saved successfully.")
        self.profile_saved.emit(profile)

    def _show_error(self, message: str) -> None:
        """Display a profile validation error."""

        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #B42318; font-weight: 600;")
        self._status_label.setVisible(True)

    def _show_success(self, message: str) -> None:
        """Display successful-save feedback."""

        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #2E6A45; font-weight: 600;")
        self._status_label.setVisible(True)
