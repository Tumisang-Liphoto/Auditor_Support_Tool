"""Application appearance configuration page."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    resolve_effective_mode,
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

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        self._mode_buttons: dict[str, QPushButton] = {}
        self._status_label = QLabel()

        self._preview_canvas = QFrame()
        self._preview_sidebar = QFrame()
        self._preview_surface = QFrame()
        self._preview_title = QLabel()
        self._preview_text = QLabel()
        self._preview_accent = QFrame()

        self._build_interface()
        self.load_appearance()

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

        page_title = QLabel("Appearance")
        page_title.setObjectName("pageTitle")

        page_subtitle = QLabel(
            "Choose how the Auditor Support Tool should appear on this computer."
        )
        page_subtitle.setObjectName("pageSubtitle")
        page_subtitle.setWordWrap(True)

        settings_panel = QFrame()
        settings_panel.setObjectName("settingsPanel")
        settings_panel.setMaximumWidth(1040)
        settings_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        panel_layout = QVBoxLayout(settings_panel)
        panel_layout.setContentsMargins(28, 26, 28, 26)
        panel_layout.setSpacing(24)

        eyebrow = QLabel("PERSONALISATION")
        eyebrow.setObjectName("settingsEyebrow")

        panel_title = QLabel("Application appearance")
        panel_title.setObjectName("settingsPanelTitle")

        panel_description = QLabel(
            "Appearance preferences are saved locally and applied whenever the application starts."
        )
        panel_description.setObjectName("settingsPanelDescription")
        panel_description.setWordWrap(True)

        divider = QFrame()
        divider.setObjectName("horizontalDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        body_layout = QGridLayout()
        body_layout.setHorizontalSpacing(32)
        body_layout.setVerticalSpacing(16)
        body_layout.setColumnStretch(0, 5)
        body_layout.setColumnStretch(1, 4)

        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(14)

        theme_title = QLabel("Colour theme")
        theme_title.setObjectName("settingsSectionTitle")

        theme_description = QLabel(
            "The colour theme controls the primary accent and navigation "
            "identity used throughout the application."
        )
        theme_description.setObjectName("settingsSectionDescription")
        theme_description.setWordWrap(True)

        theme_option = self._build_theme_option()

        mode_title = QLabel("Appearance mode")
        mode_title.setObjectName("settingsSectionTitle")

        mode_description = QLabel(
            "Use the Windows setting automatically or select a fixed appearance."
        )
        mode_description.setObjectName("settingsSectionDescription")
        mode_description.setWordWrap(True)

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(10)

        mode_definitions = (
            ("system", "System", "Follow Windows"),
            ("light", "Light", "Bright workspace"),
            ("dark", "Dark", "Reduced glare"),
        )

        for mode_key, title, description in mode_definitions:
            button = QPushButton(f"{title}\n{description}")
            button.setObjectName("appearanceModeButton")
            button.setCheckable(True)
            button.setProperty("modeKey", mode_key)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            button.toggled.connect(
                lambda checked, key=mode_key: self._update_preview(key) if checked else None
            )

            self._mode_group.addButton(button)
            self._mode_buttons[mode_key] = button
            mode_layout.addWidget(button)

        controls_layout.addWidget(theme_title)
        controls_layout.addWidget(theme_description)
        controls_layout.addWidget(theme_option)
        controls_layout.addSpacing(12)
        controls_layout.addWidget(mode_title)
        controls_layout.addWidget(mode_description)
        controls_layout.addLayout(mode_layout)
        controls_layout.addStretch()

        preview_panel = self._build_preview_panel()

        body_layout.addLayout(controls_layout, 0, 0)
        body_layout.addWidget(preview_panel, 0, 1)

        action_layout = QHBoxLayout()
        action_layout.setSpacing(16)

        self._status_label.setObjectName("formStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        apply_button = QPushButton("Apply Appearance")
        apply_button.setObjectName("primaryActionButton")
        apply_button.setMinimumWidth(165)
        apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button.clicked.connect(self.apply_appearance)

        action_layout.addWidget(self._status_label, 1)
        action_layout.addWidget(apply_button)

        panel_layout.addWidget(eyebrow)
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(panel_description)
        panel_layout.addWidget(divider)
        panel_layout.addLayout(body_layout)
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

    def _build_theme_option(self) -> QFrame:
        option = QFrame()
        option.setObjectName("themeOption")

        layout = QHBoxLayout(option)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        swatch = QFrame()
        swatch.setObjectName("themeSwatch")
        swatch.setFixedSize(38, 38)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)

        theme_name = QLabel(THEME_DISPLAY_NAMES["mint_green"])
        theme_name.setObjectName("themeName")

        theme_description = QLabel("A calm professional palette using #81D185.")
        theme_description.setObjectName("fieldHint")

        selected_badge = QLabel("SELECTED")
        selected_badge.setObjectName("selectedBadge")

        text_layout.addWidget(theme_name)
        text_layout.addWidget(theme_description)

        layout.addWidget(swatch)
        layout.addLayout(text_layout, 1)
        layout.addWidget(selected_badge)

        return option

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("appearancePreviewPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Preview")
        title.setObjectName("settingsSectionTitle")

        description = QLabel("A simplified preview of the selected appearance.")
        description.setObjectName("fieldHint")
        description.setWordWrap(True)

        self._preview_canvas.setObjectName("appearancePreviewCanvas")
        self._preview_canvas.setMinimumHeight(230)

        canvas_layout = QHBoxLayout(self._preview_canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        self._preview_sidebar.setObjectName("appearancePreviewSidebar")
        self._preview_sidebar.setFixedWidth(64)

        sidebar_layout = QVBoxLayout(self._preview_sidebar)
        sidebar_layout.setContentsMargins(10, 14, 10, 14)
        sidebar_layout.setSpacing(9)

        preview_brand = QLabel("A")
        preview_brand.setObjectName("appearancePreviewBrand")
        preview_brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_brand.setFixedSize(30, 30)

        for width in (38, 30, 34):
            item = QFrame()
            item.setObjectName("appearancePreviewNavItem")
            item.setFixedSize(width, 7)
            sidebar_layout.addWidget(item)

        sidebar_layout.insertWidget(0, preview_brand)
        sidebar_layout.addStretch()

        preview_content = QWidget()
        preview_content.setObjectName("appearancePreviewContent")

        content_layout = QVBoxLayout(preview_content)
        content_layout.setContentsMargins(18, 18, 18, 18)
        content_layout.setSpacing(10)

        self._preview_title.setObjectName("appearancePreviewTitle")
        self._preview_title.setText("Dashboard")

        self._preview_text.setObjectName("appearancePreviewText")
        self._preview_text.setText("Audit engagement overview")

        self._preview_surface.setObjectName("appearancePreviewSurface")

        surface_layout = QVBoxLayout(self._preview_surface)
        surface_layout.setContentsMargins(14, 14, 14, 14)
        surface_layout.setSpacing(8)

        surface_title = QLabel("Current engagement")
        surface_title.setObjectName("appearancePreviewCardTitle")

        surface_text = QLabel("No engagement selected")
        surface_text.setObjectName("appearancePreviewCardText")

        self._preview_accent.setObjectName("appearancePreviewAccent")
        self._preview_accent.setFixedSize(88, 10)

        surface_layout.addWidget(surface_title)
        surface_layout.addWidget(surface_text)
        surface_layout.addStretch()
        surface_layout.addWidget(self._preview_accent)

        content_layout.addWidget(self._preview_title)
        content_layout.addWidget(self._preview_text)
        content_layout.addWidget(self._preview_surface, 1)

        canvas_layout.addWidget(self._preview_sidebar)
        canvas_layout.addWidget(preview_content, 1)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self._preview_canvas)

        return panel

    def load_appearance(self) -> None:
        """Load the saved appearance into the controls."""

        appearance = self._settings_service.get_appearance()

        button = self._mode_buttons.get(
            appearance.mode,
            self._mode_buttons["system"],
        )
        button.setChecked(True)

        self._update_preview(appearance.mode)

    def apply_appearance(self) -> None:
        """Apply and persist the selected appearance."""

        selected_button = self._mode_group.checkedButton()

        if selected_button is None:
            self._show_status(
                "Select an appearance mode.",
                "error",
            )
            return

        mode = str(selected_button.property("modeKey"))

        appearance = AppearanceSettings(
            theme="mint_green",
            mode=mode,
        )

        try:
            self._theme_service.apply_appearance(
                appearance,
                persist=True,
            )
        except ValueError as error:
            self._show_status(
                str(error),
                "error",
            )
            return

        self._show_status(
            (
                f"{THEME_DISPLAY_NAMES[appearance.theme]} using "
                f"{MODE_DISPLAY_NAMES[appearance.mode]} mode has "
                "been applied."
            ),
            "success",
        )

    def _update_preview(self, selected_mode: str) -> None:
        application = QApplication.instance()

        if isinstance(application, QApplication):
            system_scheme = application.styleHints().colorScheme()
        else:
            system_scheme = Qt.ColorScheme.Light

        effective_mode = resolve_effective_mode(
            selected_mode,
            system_scheme,
        )

        if effective_mode == "dark":
            palette = {
                "canvas": "#171C18",
                "content": "#202621",
                "surface": "#282F29",
                "sidebar": "#10271E",
                "text": "#F1F5F1",
                "muted": "#B7C2B8",
                "border": "#39423A",
                "nav": "#345646",
            }
        else:
            palette = {
                "canvas": "#F7FAF7",
                "content": "#F7FAF7",
                "surface": "#FFFFFF",
                "sidebar": "#173A2C",
                "text": "#1F2A22",
                "muted": "#5D6B60",
                "border": "#D9E5DB",
                "nav": "#4E715F",
            }

        self._preview_canvas.setStyleSheet(
            f"""
            QFrame#appearancePreviewCanvas {{
                background: {palette["canvas"]};
                border: 1px solid {palette["border"]};
                border-radius: 9px;
            }}

            QFrame#appearancePreviewSidebar {{
                background: {palette["sidebar"]};
                border: none;
                border-top-left-radius: 9px;
                border-bottom-left-radius: 9px;
            }}

            QLabel#appearancePreviewBrand {{
                background: #81D185;
                color: #173A2C;
                border-radius: 15px;
                font-weight: 700;
            }}

            QFrame#appearancePreviewNavItem {{
                background: {palette["nav"]};
                border: none;
                border-radius: 3px;
            }}

            QWidget#appearancePreviewContent {{
                background: {palette["content"]};
                border-top-right-radius: 9px;
                border-bottom-right-radius: 9px;
            }}

            QLabel#appearancePreviewTitle {{
                color: {palette["text"]};
                font-size: 13pt;
                font-weight: 700;
            }}

            QLabel#appearancePreviewText {{
                color: {palette["muted"]};
            }}

            QFrame#appearancePreviewSurface {{
                background: {palette["surface"]};
                border: 1px solid {palette["border"]};
                border-radius: 7px;
            }}

            QLabel#appearancePreviewCardTitle {{
                color: {palette["text"]};
                font-weight: 700;
            }}

            QLabel#appearancePreviewCardText {{
                color: {palette["muted"]};
            }}

            QFrame#appearancePreviewAccent {{
                background: #81D185;
                border: none;
                border-radius: 5px;
            }}
            """
        )

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
