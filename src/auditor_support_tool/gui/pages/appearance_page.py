"""Application appearance configuration page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.services.settings_service import (
    AppearanceSettings,
    SettingsService,
)
from auditor_support_tool.services.theme_service import (
    MODE_DISPLAY_NAMES,
    THEME_DISPLAY_NAMES,
    ThemeService,
)


class AppearancePage(QWidget):
    """Configure the application theme and appearance mode."""

    def __init__(
        self,
        settings_service: SettingsService,
        theme_service: ThemeService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings_service = settings_service
        self._theme_service = theme_service

        self._theme_input = QComboBox()
        self._mode_input = QComboBox()
        self._status_label = QLabel()

        self._build_interface()
        self.load_appearance()

    def _build_interface(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel("Appearance")
        title.setObjectName("pageTitle")

        subtitle = QLabel(
            "Select the visual theme and choose whether the application "
            "uses Light, Dark or the current Windows appearance."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)

        settings_card = QFrame()
        settings_card.setObjectName("card")
        settings_card.setMaximumWidth(720)

        card_layout = QVBoxLayout(settings_card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(16)

        card_title = QLabel("Application Theme")
        card_title.setObjectName("cardTitle")

        card_text = QLabel(
            "Mint Green uses #81D185 as the primary application accent. "
            "Additional colour themes can be introduced later."
        )
        card_text.setObjectName("cardText")
        card_text.setWordWrap(True)

        self._theme_input.setObjectName("formInput")

        for theme_key, display_name in THEME_DISPLAY_NAMES.items():
            self._theme_input.addItem(
                display_name,
                theme_key,
            )

        self._mode_input.setObjectName("formInput")

        for mode_key, display_name in MODE_DISPLAY_NAMES.items():
            self._mode_input.addItem(
                display_name,
                mode_key,
            )

        form_layout = QFormLayout()
        form_layout.setHorizontalSpacing(22)
        form_layout.setVerticalSpacing(14)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        form_layout.addRow(
            "Colour theme",
            self._theme_input,
        )
        form_layout.addRow(
            "Appearance mode",
            self._mode_input,
        )

        preview_card = QFrame()
        preview_card.setObjectName("card")

        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(18, 16, 18, 16)
        preview_layout.setSpacing(6)

        preview_title = QLabel("Theme Preview")
        preview_title.setObjectName("cardTitle")

        preview_text = QLabel(
            "This preview uses the same cards, text and accent controls "
            "used throughout the Auditor Support Tool."
        )
        preview_text.setObjectName("cardText")
        preview_text.setWordWrap(True)

        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(preview_text)

        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        apply_button = QPushButton("Apply Appearance")
        apply_button.setObjectName("primaryActionButton")
        apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button.clicked.connect(self.apply_appearance)

        card_layout.addWidget(card_title)
        card_layout.addWidget(card_text)
        card_layout.addLayout(form_layout)
        card_layout.addWidget(preview_card)
        card_layout.addWidget(self._status_label)
        card_layout.addWidget(
            apply_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(
            settings_card,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addStretch()

    def load_appearance(self) -> None:
        """Load the saved appearance into the controls."""

        appearance = self._settings_service.get_appearance()

        self._select_combo_value(
            combo=self._theme_input,
            value=appearance.theme,
        )
        self._select_combo_value(
            combo=self._mode_input,
            value=appearance.mode,
        )

    def apply_appearance(self) -> None:
        """Apply and persist the selected appearance."""

        theme = self._theme_input.currentData()
        mode = self._mode_input.currentData()

        appearance = AppearanceSettings(
            theme=str(theme),
            mode=str(mode),
        )

        try:
            self._theme_service.apply_appearance(
                appearance,
                persist=True,
            )
        except ValueError as error:
            self._show_error(str(error))
            return

        mode_name = MODE_DISPLAY_NAMES[appearance.mode]
        theme_name = THEME_DISPLAY_NAMES[appearance.theme]

        self._show_success(f"{theme_name} using {mode_name} mode has been applied.")

    @staticmethod
    def _select_combo_value(
        combo: QComboBox,
        value: str,
    ) -> None:
        """Select a combo item using its stored data value."""

        index = combo.findData(value)

        if index >= 0:
            combo.setCurrentIndex(index)

    def _show_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #B42318; font-weight: 600;")
        self._status_label.setVisible(True)

    def _show_success(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #2E6A45; font-weight: 600;")
        self._status_label.setVisible(True)
