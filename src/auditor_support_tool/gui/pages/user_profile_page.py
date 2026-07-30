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
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        panel_layout.setContentsMargins(30, 28, 30, 28)
        panel_layout.setSpacing(24)

        header_layout = self._build_header()

        top_divider = self._create_divider()
        bottom_divider = self._create_divider()

        section_title = QLabel("Profile details")
        section_title.setObjectName("settingsSectionTitle")

        section_description = QLabel("Fields marked with an asterisk are required.")
        section_description.setObjectName("settingsSectionDescription")

        self._configure_inputs()

        form_layout = QGridLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(24)
        form_layout.setVerticalSpacing(22)
        form_layout.setColumnStretch(0, 1)
        form_layout.setColumnStretch(1, 1)

        display_name_field = self._create_field(
            label_text="Display name *",
            control=self._display_name_input,
            hint_text=("The name shown in engagement records and reports."),
        )

        role_field = self._create_field(
            label_text="Role",
            control=self._role_input,
            hint_text="Your audit or organisational role.",
        )

        organization_field = self._create_field(
            label_text="Organisation *",
            control=self._organization_input,
            hint_text=("The organisation or audit institution represented."),
        )

        currency_field = self._create_field(
            label_text="Default currency",
            control=self._currency_input,
            hint_text=("Used as the initial currency for financial engagements."),
        )

        form_layout.addWidget(display_name_field, 0, 0)
        form_layout.addWidget(role_field, 0, 1)
        form_layout.addWidget(organization_field, 1, 0, 1, 2)
        form_layout.addWidget(currency_field, 2, 0)

        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(16)

        self._status_label.setObjectName("formStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        save_button = QPushButton("Save Profile")
        save_button.setObjectName("primaryActionButton")
        save_button.setFixedWidth(150)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.clicked.connect(self.save_profile)

        actions_layout.addWidget(self._status_label)
        actions_layout.addStretch(1)
        actions_layout.addWidget(save_button)

        panel_layout.addLayout(header_layout)
        panel_layout.addWidget(top_divider)
        panel_layout.addWidget(section_title)
        panel_layout.addWidget(section_description)
        panel_layout.addLayout(form_layout)
        panel_layout.addWidget(bottom_divider)
        panel_layout.addLayout(actions_layout)

        page_layout.addWidget(page_title)
        page_layout.addWidget(page_subtitle)

        # Do not use AlignLeft here. Allow the panel to expand up to
        # its maximum width instead of remaining at its natural size.
        page_layout.addWidget(settings_panel)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_header(self) -> QHBoxLayout:
        """Build the profile panel header."""

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(18)

        self._avatar_label.setObjectName("profileAvatar")
        self._avatar_label.setFixedSize(64, 64)
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        eyebrow = QLabel("LOCAL PROFILE")
        eyebrow.setObjectName("settingsEyebrow")

        panel_title = QLabel("Auditor information")
        panel_title.setObjectName("settingsPanelTitle")

        panel_description = QLabel(
            "This information is stored locally on this computer and is "
            "not automatically shared outside the application."
        )
        panel_description.setObjectName("settingsPanelDescription")
        panel_description.setWordWrap(True)

        text_layout.addWidget(eyebrow)
        text_layout.addWidget(panel_title)
        text_layout.addWidget(panel_description)

        privacy_badge = QLabel("STORED LOCALLY")
        privacy_badge.setObjectName("privacyBadge")
        privacy_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(
            self._avatar_label,
            0,
            Qt.AlignmentFlag.AlignTop,
        )
        header_layout.addLayout(text_layout, 1)
        header_layout.addWidget(
            privacy_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        return header_layout

    def _configure_inputs(self) -> None:
        """Configure the profile input controls."""

        inputs = (
            self._display_name_input,
            self._organization_input,
            self._role_input,
        )

        for input_control in inputs:
            input_control.setObjectName("formInput")
            input_control.setMinimumHeight(44)
            input_control.setClearButtonEnabled(True)

        self._display_name_input.setPlaceholderText("For example: Tumisang Liphoto")
        self._display_name_input.textChanged.connect(self._update_avatar)

        self._organization_input.setPlaceholderText("For example: Office of the Auditor-General")

        self._role_input.setPlaceholderText("For example: Auditor")

        self._currency_input.setObjectName("formInput")
        self._currency_input.setMinimumHeight(44)
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
    def _create_field(
        label_text: str,
        control: QWidget,
        hint_text: str,
    ) -> QWidget:
        """Create a vertically arranged form field."""

        field = QWidget()
        field.setObjectName("formField")

        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")

        hint = QLabel(hint_text)
        hint.setObjectName("fieldHint")
        hint.setWordWrap(True)

        layout.addWidget(label)
        layout.addWidget(control)
        layout.addWidget(hint)

        return field

    @staticmethod
    def _create_divider() -> QFrame:
        """Create a horizontal section divider."""

        divider = QFrame()
        divider.setObjectName("horizontalDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        return divider

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
        """Update the avatar using the entered initials."""

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
        """Display save or validation feedback."""

        self._status_label.setText(message)
        self._status_label.setProperty("status", status)
        self._status_label.setVisible(True)

        style = self._status_label.style()
        style.unpolish(self._status_label)
        style.polish(self._status_label)
