"""Local user-profile setup and maintenance page."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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

        self._avatar_label = QLabel("AU")
        self._display_name_input = QLineEdit()
        self._organization_input = QLineEdit()
        self._role_input = QLineEdit()
        self._currency_input = QComboBox()
        self._status_label = QLabel()

        self._build_interface()
        self.load_profile()

    def _build_interface(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("pageScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("pageContent")

        page_layout = QVBoxLayout(content)
        page_layout.setContentsMargins(40, 32, 40, 32)
        page_layout.setSpacing(22)

        page_title = QLabel("User Profile")
        page_title.setObjectName("pageTitle")

        page_subtitle = QLabel(
            "Manage the auditor information used when creating engagements "
            "and generating working papers and reports."
        )
        page_subtitle.setObjectName("pageSubtitle")
        page_subtitle.setWordWrap(True)

        settings_panel = QFrame()
        settings_panel.setObjectName("settingsPanel")
        settings_panel.setMaximumWidth(980)
        settings_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        panel_layout = QVBoxLayout(settings_panel)
        panel_layout.setContentsMargins(28, 26, 28, 26)
        panel_layout.setSpacing(24)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        self._avatar_label.setObjectName("profileAvatar")
        self._avatar_label.setFixedSize(54, 54)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(3)

        eyebrow = QLabel("LOCAL PROFILE")
        eyebrow.setObjectName("settingsEyebrow")

        panel_title = QLabel("Auditor information")
        panel_title.setObjectName("settingsPanelTitle")

        panel_description = QLabel(
            "This information is stored locally on this computer and is not "
            "automatically shared outside the application."
        )
        panel_description.setObjectName("settingsPanelDescription")
        panel_description.setWordWrap(True)

        header_text_layout.addWidget(eyebrow)
        header_text_layout.addWidget(panel_title)
        header_text_layout.addWidget(panel_description)

        privacy_badge = QLabel("STORED LOCALLY")
        privacy_badge.setObjectName("privacyBadge")
        privacy_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(self._avatar_label)
        header_layout.addLayout(header_text_layout, 1)
        header_layout.addWidget(
            privacy_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        details_title = QLabel("Profile details")
        details_title.setObjectName("settingsSectionTitle")

        details_description = QLabel("Fields marked with an asterisk are required.")
        details_description.setObjectName("settingsSectionDescription")

        self._configure_inputs()

        fields_layout = QGridLayout()
        fields_layout.setHorizontalSpacing(24)
        fields_layout.setVerticalSpacing(8)
        fields_layout.setColumnStretch(0, 1)
        fields_layout.setColumnStretch(1, 1)

        fields_layout.addWidget(
            self._create_field_label("Display name *"),
            0,
            0,
        )
        fields_layout.addWidget(
            self._create_field_label("Role"),
            0,
            1,
        )
        fields_layout.addWidget(
            self._display_name_input,
            1,
            0,
        )
        fields_layout.addWidget(
            self._role_input,
            1,
            1,
        )
        fields_layout.addWidget(
            self._create_field_hint("The name shown in engagement records and reports."),
            2,
            0,
        )
        fields_layout.addWidget(
            self._create_field_hint("Your audit or organisational role."),
            2,
            1,
        )

        fields_layout.addWidget(
            self._create_field_label("Organisation *"),
            3,
            0,
            1,
            2,
        )
        fields_layout.addWidget(
            self._organization_input,
            4,
            0,
            1,
            2,
        )
        fields_layout.addWidget(
            self._create_field_hint("The organisation or audit institution represented."),
            5,
            0,
            1,
            2,
        )

        fields_layout.addWidget(
            self._create_field_label("Default currency"),
            6,
            0,
        )
        fields_layout.addWidget(
            self._currency_input,
            7,
            0,
        )
        fields_layout.addWidget(
            self._create_field_hint("Used as the initial currency for financial engagements."),
            8,
            0,
        )

        divider = QFrame()
        divider.setObjectName("horizontalDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(16)

        self._status_label.setObjectName("formStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        save_button = QPushButton("Save Profile")
        save_button.setObjectName("primaryActionButton")
        save_button.setMinimumWidth(140)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.clicked.connect(self.save_profile)

        action_layout.addWidget(self._status_label, 1)
        action_layout.addWidget(save_button)

        panel_layout.addLayout(header_layout)
        panel_layout.addWidget(divider)
        panel_layout.addWidget(details_title)
        panel_layout.addWidget(details_description)
        panel_layout.addLayout(fields_layout)
        panel_layout.addSpacing(4)
        panel_layout.addWidget(divider)
        panel_layout.addLayout(action_layout)

        page_layout.addWidget(page_title)
        page_layout.addWidget(page_subtitle)
        page_layout.addWidget(
            settings_panel,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        page_layout.addStretch()

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _configure_inputs(self) -> None:
        self._display_name_input.setObjectName("formInput")
        self._display_name_input.setPlaceholderText("For example: Tumisang Liphoto")
        self._display_name_input.setClearButtonEnabled(True)
        self._display_name_input.textChanged.connect(self._update_avatar)

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

    @staticmethod
    def _create_field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _create_field_hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldHint")
        label.setWordWrap(True)
        return label

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

        self._update_avatar(profile.display_name)

    def save_profile(self) -> None:
        """Validate and save the local profile."""

        display_name = self._display_name_input.text().strip()
        organization = self._organization_input.text().strip()
        role = self._role_input.text().strip() or "Auditor"
        currency = self._currency_input.currentText().strip().upper() or "LSL"

        if not display_name:
            self._show_status(
                "Enter the auditor's display name.",
                "error",
            )
            self._display_name_input.setFocus()
            return

        if not organization:
            self._show_status(
                "Enter the auditor's organisation.",
                "error",
            )
            self._organization_input.setFocus()
            return

        if len(currency) != 3 or not currency.isalpha():
            self._show_status(
                "Enter a valid three-letter currency code.",
                "error",
            )
            self._currency_input.setFocus()
            return

        profile = UserProfile(
            display_name=display_name,
            organization=organization,
            role=role,
            default_currency=currency,
        )

        self._settings_service.save_user_profile(profile)

        self._show_status(
            "Profile saved successfully.",
            "success",
        )
        self.profile_saved.emit(profile)

    def _update_avatar(self, display_name: str) -> None:
        parts = [part for part in display_name.strip().split() if part]

        if not parts:
            initials = "AU"
        elif len(parts) == 1:
            initials = parts[0][:2].upper()
        else:
            initials = (parts[0][0] + parts[-1][0]).upper()

        self._avatar_label.setText(initials)

    def _show_status(
        self,
        message: str,
        status: str,
    ) -> None:
        self._status_label.setText(message)
        self._status_label.setProperty("status", status)
        self._status_label.setVisible(True)

        style = self._status_label.style()
        style.unpolish(self._status_label)
        style.polish(self._status_label)
