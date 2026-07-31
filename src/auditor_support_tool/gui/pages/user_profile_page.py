"""Local user-profile setup and maintenance page."""

import re

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

ROLE_OPTIONS = (
    "Auditor",
    "Assistant Auditor",
    "Senior Auditor",
    "Principal Auditor",
    "Audit Supervisor",
    "Audit Manager",
    "Director",
    "ICT Auditor",
    "IT Audit Manager",
    "Internal Auditor",
    "Chief Internal Auditor",
    "Finance Officer",
    "Administrator",
)


CURRENCY_OPTIONS = (
    "LSL",
    "ZAR",
    "USD",
    "EUR",
    "GBP",
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

        self._preferred_name_input = QLineEdit()
        self._full_name_input = QLineEdit()
        self._job_title_input = QComboBox()
        self._organization_input = QLineEdit()
        self._directorate_input = QLineEdit()
        self._email_input = QLineEdit()
        self._phone_input = QLineEdit()
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
            "Maintain your personal and organisational information "
            "separately from application and connection settings."
        )
        page_subtitle.setObjectName("pageSubtitle")
        page_subtitle.setWordWrap(True)

        self._configure_inputs()

        personal_card = self._create_section_card(
            title="Personal Information",
            description=(
                "This information is stored only for the current Windows "
                "user and is not sent outside the application automatically."
            ),
            fields=(
                (
                    "Preferred name",
                    True,
                    self._preferred_name_input,
                    "The name the application should use when addressing you.",
                ),
                (
                    "Full name",
                    True,
                    self._full_name_input,
                    "The full name that may appear in reports and activity records.",
                ),
                (
                    "Job title / role",
                    True,
                    self._job_title_input,
                    "Select a listed role or enter another appropriate title.",
                ),
            ),
        )

        organization_card = self._create_section_card(
            title="Organisation",
            description=(
                "These details can later be used in report headings, "
                "engagement records and exported outputs."
            ),
            fields=(
                (
                    "Organisation",
                    True,
                    self._organization_input,
                    "The audit institution or organisation represented.",
                ),
                (
                    "Directorate",
                    False,
                    self._directorate_input,
                    "The directorate, department or business unit.",
                ),
            ),
        )

        contact_card = self._create_section_card(
            title="Contact Information",
            description=("Contact details are optional and remain stored locally."),
            fields=(
                (
                    "Email address",
                    False,
                    self._email_input,
                    "Used only where a generated output requires contact details.",
                ),
                (
                    "Phone number",
                    False,
                    self._phone_input,
                    "International and local number formats are accepted.",
                ),
            ),
        )

        defaults_card = self._create_section_card(
            title="Application Defaults",
            description=(
                "Default values reduce repeated data entry when creating new audit engagements."
            ),
            fields=(
                (
                    "Default currency",
                    False,
                    self._currency_input,
                    "Used as the initial currency for financial engagements.",
                ),
            ),
        )

        action_bar = self._build_action_bar()

        page_layout.addWidget(page_title)
        page_layout.addWidget(page_subtitle)
        page_layout.addWidget(personal_card)
        page_layout.addWidget(organization_card)
        page_layout.addWidget(contact_card)
        page_layout.addWidget(defaults_card)
        page_layout.addWidget(action_bar)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

        self._set_tab_order()

    def _configure_inputs(self) -> None:
        """Configure profile controls and generic placeholders."""

        line_edits = (
            self._preferred_name_input,
            self._full_name_input,
            self._organization_input,
            self._directorate_input,
            self._email_input,
            self._phone_input,
        )

        for input_control in line_edits:
            input_control.setObjectName("formInput")
            input_control.setMinimumHeight(44)
            input_control.setClearButtonEnabled(True)

        self._preferred_name_input.setPlaceholderText("Name")
        self._full_name_input.setPlaceholderText("Name Surname")
        self._organization_input.setPlaceholderText("Organisation name")
        self._directorate_input.setPlaceholderText("Directorate or department")
        self._email_input.setPlaceholderText("name.surname@example.org")
        self._phone_input.setPlaceholderText("+266 5XXX XXXX")

        self._job_title_input.setObjectName("formInput")
        self._job_title_input.setMinimumHeight(44)
        self._job_title_input.setEditable(True)
        self._job_title_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._job_title_input.addItems(ROLE_OPTIONS)
        self._job_title_input.setCurrentIndex(-1)

        job_title_line_edit = self._job_title_input.lineEdit()

        if job_title_line_edit is not None:
            job_title_line_edit.setPlaceholderText("Select or enter a role")
            job_title_line_edit.setClearButtonEnabled(True)

        self._currency_input.setObjectName("formInput")
        self._currency_input.setMinimumHeight(44)
        self._currency_input.setEditable(True)
        self._currency_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._currency_input.addItems(CURRENCY_OPTIONS)

    def _create_section_card(
        self,
        title: str,
        description: str,
        fields: tuple[
            tuple[str, bool, QWidget, str],
            ...,
        ],
    ) -> QFrame:
        """Create a full-width profile section."""

        card = QFrame()
        card.setObjectName("profileSectionCard")
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 26, 30, 26)
        card_layout.setSpacing(18)

        section_title = QLabel(title)
        section_title.setObjectName("profileSectionTitle")

        section_description = QLabel(description)
        section_description.setObjectName("profileSectionDescription")
        section_description.setWordWrap(True)

        fields_layout = QGridLayout()
        fields_layout.setContentsMargins(0, 4, 0, 0)
        fields_layout.setHorizontalSpacing(24)
        fields_layout.setVerticalSpacing(18)
        fields_layout.setColumnMinimumWidth(0, 150)
        fields_layout.setColumnStretch(1, 1)

        for row, (
            label_text,
            required,
            control,
            hint_text,
        ) in enumerate(fields):
            label = self._create_field_label(
                text=label_text,
                required=required,
            )
            field_container = self._create_field_container(
                control=control,
                hint_text=hint_text,
            )

            fields_layout.addWidget(
                label,
                row,
                0,
                Qt.AlignmentFlag.AlignTop,
            )
            fields_layout.addWidget(
                field_container,
                row,
                1,
            )

        card_layout.addWidget(section_title)
        card_layout.addWidget(section_description)
        card_layout.addLayout(fields_layout)

        return card

    @staticmethod
    def _create_field_label(
        text: str,
        required: bool,
    ) -> QWidget:
        """Create a label with an optional red required marker."""

        container = QWidget()
        container.setObjectName("fieldLabelContainer")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(4)

        label = QLabel(text)
        label.setObjectName("fieldLabel")

        layout.addWidget(label)

        if required:
            required_marker = QLabel("*")
            required_marker.setObjectName("requiredAsterisk")
            required_marker.setToolTip("Required field")
            layout.addWidget(required_marker)

        layout.addStretch()

        return container

    @staticmethod
    def _create_field_container(
        control: QWidget,
        hint_text: str,
    ) -> QWidget:
        """Create an input with its supporting guidance."""

        container = QWidget()
        container.setObjectName("formField")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hint = QLabel(hint_text)
        hint.setObjectName("fieldHint")
        hint.setWordWrap(True)

        layout.addWidget(control)
        layout.addWidget(hint)

        return container

    def _build_action_bar(self) -> QFrame:
        """Create the save and validation action bar."""

        action_bar = QFrame()
        action_bar.setObjectName("profileActionBar")

        layout = QHBoxLayout(action_bar)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(16)

        self._status_label.setObjectName("formStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        save_button = QPushButton("Save Profile")
        save_button.setObjectName("primaryActionButton")
        save_button.setFixedWidth(150)
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.clicked.connect(self.save_profile)

        layout.addWidget(self._status_label, 1)
        layout.addWidget(save_button)

        return action_bar

    def _set_tab_order(self) -> None:
        """Define a predictable keyboard-navigation order."""

        self.setTabOrder(
            self._preferred_name_input,
            self._full_name_input,
        )
        self.setTabOrder(
            self._full_name_input,
            self._job_title_input,
        )
        self.setTabOrder(
            self._job_title_input,
            self._organization_input,
        )
        self.setTabOrder(
            self._organization_input,
            self._directorate_input,
        )
        self.setTabOrder(
            self._directorate_input,
            self._email_input,
        )
        self.setTabOrder(
            self._email_input,
            self._phone_input,
        )
        self.setTabOrder(
            self._phone_input,
            self._currency_input,
        )

    def load_profile(self) -> None:
        """Load the saved profile into the form."""

        profile = self._settings_service.get_user_profile()

        self._preferred_name_input.setText(profile.preferred_name)
        self._full_name_input.setText(profile.full_name)
        self._organization_input.setText(profile.organization)
        self._directorate_input.setText(profile.directorate)
        self._email_input.setText(profile.email_address)
        self._phone_input.setText(profile.phone_number)

        self._select_or_enter_combo_value(
            combo=self._job_title_input,
            value=profile.job_title,
        )
        self._select_or_enter_combo_value(
            combo=self._currency_input,
            value=profile.default_currency,
        )

    def save_profile(self) -> None:
        """Validate and save the local profile."""

        self._clear_validation_errors()

        preferred_name = self._preferred_name_input.text().strip()
        full_name = self._full_name_input.text().strip()
        job_title = self._job_title_input.currentText().strip()
        organization = self._organization_input.text().strip()
        directorate = self._directorate_input.text().strip()
        email_address = self._email_input.text().strip()
        phone_number = self._phone_input.text().strip()
        default_currency = self._currency_input.currentText().strip().upper() or "LSL"

        required_fields = (
            (
                self._preferred_name_input,
                preferred_name,
                "Enter a preferred name.",
            ),
            (
                self._full_name_input,
                full_name,
                "Enter the auditor's full name.",
            ),
            (
                self._job_title_input,
                job_title,
                "Select or enter a job title or role.",
            ),
            (
                self._organization_input,
                organization,
                "Enter the organisation name.",
            ),
        )

        for control, value, message in required_fields:
            if not value:
                self._mark_invalid(control)
                self._show_status(message, "error")
                control.setFocus()
                return

        if email_address and not self._is_valid_email(email_address):
            self._mark_invalid(self._email_input)
            self._show_status(
                "Enter a valid email address.",
                "error",
            )
            self._email_input.setFocus()
            return

        if phone_number and not self._is_valid_phone(phone_number):
            self._mark_invalid(self._phone_input)
            self._show_status(
                "Enter a valid phone number.",
                "error",
            )
            self._phone_input.setFocus()
            return

        if len(default_currency) != 3 or not default_currency.isalpha():
            self._mark_invalid(self._currency_input)
            self._show_status(
                "Enter a valid three-letter currency code.",
                "error",
            )
            self._currency_input.setFocus()
            return

        profile = UserProfile(
            preferred_name=preferred_name,
            full_name=full_name,
            job_title=job_title,
            organization=organization,
            directorate=directorate,
            email_address=email_address,
            phone_number=phone_number,
            default_currency=default_currency,
        )

        self._settings_service.save_user_profile(profile)

        self._show_status(
            "Profile saved successfully.",
            "success",
        )
        self.profile_saved.emit(profile)

    def _clear_validation_errors(self) -> None:
        controls = (
            self._preferred_name_input,
            self._full_name_input,
            self._job_title_input,
            self._organization_input,
            self._directorate_input,
            self._email_input,
            self._phone_input,
            self._currency_input,
        )

        for control in controls:
            self._set_validation_state(
                control,
                "",
            )

    def _mark_invalid(self, control: QWidget) -> None:
        self._set_validation_state(
            control,
            "error",
        )

    @staticmethod
    def _set_validation_state(
        control: QWidget,
        state: str,
    ) -> None:
        control.setProperty("validationState", state)

        style = control.style()
        style.unpolish(control)
        style.polish(control)
        control.update()

    @staticmethod
    def _select_or_enter_combo_value(
        combo: QComboBox,
        value: str,
    ) -> None:
        value = value.strip()
        index = combo.findText(
            value,
            Qt.MatchFlag.MatchFixedString,
        )

        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentText(value)

    @staticmethod
    def _is_valid_email(email_address: str) -> bool:
        return bool(
            re.fullmatch(
                r"[^@\s]+@[^@\s]+\.[^@\s]+",
                email_address,
            )
        )

    @staticmethod
    def _is_valid_phone(phone_number: str) -> bool:
        if not re.fullmatch(
            r"[0-9+\-()\s]+",
            phone_number,
        ):
            return False

        digit_count = sum(character.isdigit() for character in phone_number)

        return digit_count >= 7

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
