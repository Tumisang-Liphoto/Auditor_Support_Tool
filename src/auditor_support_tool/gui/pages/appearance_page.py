"""Application appearance configuration page."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
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
    THEME_DEFINITIONS,
    ThemeService,
    get_theme_definition,
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

        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)

        self._theme_buttons: dict[str, QPushButton] = {}
        self._mode_buttons: dict[str, QPushButton] = {}

        self._status_label = QLabel()
        self._preview_selection_label = QLabel()

        self._preview_canvas = QFrame()
        self._preview_sidebar = QFrame()
        self._preview_title = QLabel()
        self._preview_text = QLabel()
        self._preview_surface = QFrame()
        self._preview_accent = QFrame()
        self._preview_action = QLabel()

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
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        page_title = QLabel("Appearance")
        page_title.setObjectName("pageTitle")

        page_subtitle = QLabel(
            "Choose the colour theme and display mode used throughout the Auditor Support Tool."
        )
        page_subtitle.setObjectName("pageSubtitle")
        page_subtitle.setWordWrap(True)

        settings_panel = QFrame()
        settings_panel.setObjectName("settingsPanel")
        settings_panel.setMaximumWidth(1080)
        settings_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        panel_layout = QVBoxLayout(settings_panel)
        panel_layout.setContentsMargins(30, 28, 30, 28)
        panel_layout.setSpacing(24)

        eyebrow = QLabel("PERSONALISATION")
        eyebrow.setObjectName("settingsEyebrow")

        panel_title = QLabel("Application appearance")
        panel_title.setObjectName("settingsPanelTitle")

        panel_description = QLabel(
            "Theme and display preferences are stored locally and applied "
            "whenever the application starts."
        )
        panel_description.setObjectName("settingsPanelDescription")
        panel_description.setWordWrap(True)

        top_divider = self._create_divider()
        bottom_divider = self._create_divider()

        theme_title = QLabel("Colour theme")
        theme_title.setObjectName("settingsSectionTitle")

        theme_description = QLabel(
            "Select a professional colour family for navigation, buttons, "
            "focus indicators and highlighted controls."
        )
        theme_description.setObjectName("settingsSectionDescription")
        theme_description.setWordWrap(True)

        theme_grid = self._build_theme_grid()

        mode_title = QLabel("Appearance mode")
        mode_title.setObjectName("settingsSectionTitle")

        mode_description = QLabel(
            "Follow the current Windows appearance or use a fixed Light or Dark mode."
        )
        mode_description.setObjectName("settingsSectionDescription")
        mode_description.setWordWrap(True)

        mode_layout = self._build_mode_layout()
        preview_panel = self._build_preview_panel()
        action_layout = self._build_action_layout()

        panel_layout.addWidget(eyebrow)
        panel_layout.addWidget(panel_title)
        panel_layout.addWidget(panel_description)
        panel_layout.addWidget(top_divider)

        panel_layout.addWidget(theme_title)
        panel_layout.addWidget(theme_description)
        panel_layout.addLayout(theme_grid)

        panel_layout.addSpacing(4)
        panel_layout.addWidget(mode_title)
        panel_layout.addWidget(mode_description)
        panel_layout.addLayout(mode_layout)

        panel_layout.addSpacing(4)
        panel_layout.addWidget(preview_panel)
        panel_layout.addWidget(bottom_divider)
        panel_layout.addLayout(action_layout)

        page_layout.addWidget(page_title)
        page_layout.addWidget(page_subtitle)
        page_layout.addWidget(settings_panel)

        scroll_area.setWidget(content)
        root_layout.addWidget(scroll_area)

    def _build_theme_grid(self) -> QGridLayout:
        """Build the selectable theme-card grid."""

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        for index, (
            theme_key,
            definition,
        ) in enumerate(THEME_DEFINITIONS.items()):
            button = QPushButton(f"{definition['display_name']}\n{definition['description']}")
            button.setObjectName("themeChoiceButton")
            button.setCheckable(True)
            button.setProperty("themeKey", theme_key)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(76)
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            button.setIcon(self._create_colour_icon(definition["accent"]))
            button.setIconSize(QSize(30, 30))
            button.setToolTip(
                f"{definition['display_name']}: "
                f"{definition['description']} "
                f"({definition['accent']})"
            )

            button.toggled.connect(
                lambda checked, selected_theme=theme_key: (
                    self._handle_theme_selected(selected_theme) if checked else None
                )
            )

            self._theme_group.addButton(button)
            self._theme_buttons[theme_key] = button

            row = index // 2
            column = index % 2

            grid.addWidget(button, row, column)

        return grid

    def _build_mode_layout(self) -> QHBoxLayout:
        """Build the System, Light and Dark mode controls."""

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

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
                lambda checked, selected_mode=mode_key: (
                    self._handle_mode_selected(selected_mode) if checked else None
                )
            )

            self._mode_group.addButton(button)
            self._mode_buttons[mode_key] = button
            layout.addWidget(button)

        return layout

    def _build_preview_panel(self) -> QFrame:
        """Build the live theme preview."""

        panel = QFrame()
        panel.setObjectName("appearancePreviewPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        heading_layout = QHBoxLayout()
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(12)

        heading_text_layout = QVBoxLayout()
        heading_text_layout.setSpacing(3)

        title = QLabel("Live preview")
        title.setObjectName("settingsSectionTitle")

        description = QLabel("The preview changes before the selection is applied.")
        description.setObjectName("fieldHint")
        description.setWordWrap(True)

        self._preview_selection_label.setObjectName("selectedBadge")
        self._preview_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading_text_layout.addWidget(title)
        heading_text_layout.addWidget(description)

        heading_layout.addLayout(heading_text_layout, 1)
        heading_layout.addWidget(
            self._preview_selection_label,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        self._preview_canvas.setObjectName("appearancePreviewCanvas")
        self._preview_canvas.setMinimumHeight(260)

        canvas_layout = QHBoxLayout(self._preview_canvas)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        self._preview_sidebar.setObjectName("appearancePreviewSidebar")
        self._preview_sidebar.setFixedWidth(84)

        sidebar_layout = QVBoxLayout(self._preview_sidebar)
        sidebar_layout.setContentsMargins(14, 16, 14, 16)
        sidebar_layout.setSpacing(11)

        preview_brand = QLabel("A")
        preview_brand.setObjectName("appearancePreviewBrand")
        preview_brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_brand.setFixedSize(34, 34)

        sidebar_layout.addWidget(
            preview_brand,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        sidebar_layout.addSpacing(10)

        for width in (46, 38, 44, 34):
            navigation_item = QFrame()
            navigation_item.setObjectName("appearancePreviewNavItem")
            navigation_item.setFixedSize(width, 8)

            sidebar_layout.addWidget(
                navigation_item,
                0,
                Qt.AlignmentFlag.AlignHCenter,
            )

        sidebar_layout.addStretch()

        preview_content = QWidget()
        preview_content.setObjectName("appearancePreviewContent")

        content_layout = QVBoxLayout(preview_content)
        content_layout.setContentsMargins(22, 20, 22, 20)
        content_layout.setSpacing(10)

        self._preview_title.setObjectName("appearancePreviewTitle")
        self._preview_title.setText("Dashboard")

        self._preview_text.setObjectName("appearancePreviewText")
        self._preview_text.setText("Audit engagement overview")

        self._preview_surface.setObjectName("appearancePreviewSurface")

        surface_layout = QVBoxLayout(self._preview_surface)
        surface_layout.setContentsMargins(18, 16, 18, 16)
        surface_layout.setSpacing(8)

        surface_title = QLabel("Current engagement")
        surface_title.setObjectName("appearancePreviewCardTitle")

        surface_text = QLabel("No engagement selected")
        surface_text.setObjectName("appearancePreviewCardText")

        self._preview_accent.setObjectName("appearancePreviewAccent")
        self._preview_accent.setFixedSize(120, 8)

        self._preview_action.setObjectName("appearancePreviewAction")
        self._preview_action.setText("Create engagement")
        self._preview_action.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_action.setFixedSize(132, 30)

        surface_layout.addWidget(surface_title)
        surface_layout.addWidget(surface_text)
        surface_layout.addStretch()
        surface_layout.addWidget(self._preview_accent)
        surface_layout.addSpacing(4)
        surface_layout.addWidget(self._preview_action)

        content_layout.addWidget(self._preview_title)
        content_layout.addWidget(self._preview_text)
        content_layout.addWidget(
            self._preview_surface,
            1,
        )

        canvas_layout.addWidget(self._preview_sidebar)
        canvas_layout.addWidget(preview_content, 1)

        layout.addLayout(heading_layout)
        layout.addWidget(self._preview_canvas)

        return panel

    def _build_action_layout(self) -> QHBoxLayout:
        """Build the appearance save actions."""

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._status_label.setObjectName("formStatus")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)

        apply_button = QPushButton("Apply Appearance")
        apply_button.setObjectName("primaryActionButton")
        apply_button.setFixedWidth(170)
        apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_button.clicked.connect(self.apply_appearance)

        layout.addWidget(self._status_label, 1)
        layout.addWidget(apply_button)

        return layout

    def load_appearance(self) -> None:
        """Load the saved appearance into the controls."""

        appearance = self._settings_service.get_appearance()

        theme_key = appearance.theme

        if theme_key not in self._theme_buttons:
            theme_key = "mint_green"

        mode_key = appearance.mode

        if mode_key not in self._mode_buttons:
            mode_key = "light"

        self._mode_buttons[mode_key].setChecked(True)
        self._theme_buttons[theme_key].setChecked(True)

        self._update_preview()

    def apply_appearance(self) -> None:
        """Apply and persist the selected appearance."""

        theme_key = self._selected_theme_key()
        mode_key = self._selected_mode_key()

        appearance = AppearanceSettings(
            theme=theme_key,
            mode=mode_key,
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

        definition = get_theme_definition(theme_key)

        self._show_status(
            (
                f"{definition['display_name']} using "
                f"{MODE_DISPLAY_NAMES[mode_key]} mode "
                "has been applied."
            ),
            "success",
        )

        self._update_preview()

    def _handle_theme_selected(
        self,
        _theme_key: str,
    ) -> None:
        """Update the preview after a theme selection."""

        self._update_preview()

    def _handle_mode_selected(
        self,
        _mode_key: str,
    ) -> None:
        """Update the preview after a mode selection."""

        self._update_preview()

    def _selected_theme_key(self) -> str:
        """Return the selected theme identifier."""

        button = self._theme_group.checkedButton()

        if button is None:
            return "mint_green"

        theme_key = str(button.property("themeKey"))

        if theme_key not in THEME_DEFINITIONS:
            return "mint_green"

        return theme_key

    def _selected_mode_key(self) -> str:
        """Return the selected mode identifier."""

        button = self._mode_group.checkedButton()

        if button is None:
            return "light"

        mode_key = str(button.property("modeKey"))

        if mode_key not in MODE_DISPLAY_NAMES:
            return "light"

        return mode_key

    def _update_preview(self) -> None:
        """Update the live theme and mode preview."""

        theme_key = self._selected_theme_key()
        selected_mode = self._selected_mode_key()
        definition = get_theme_definition(theme_key)

        application = QApplication.instance()

        if isinstance(application, QApplication):
            system_scheme = application.styleHints().colorScheme()
        else:
            system_scheme = Qt.ColorScheme.Light

        effective_mode = resolve_effective_mode(
            selected_mode=selected_mode,
            system_scheme=system_scheme,
        )

        if effective_mode == "dark":
            palette = {
                "canvas": "#171C18",
                "content": "#202621",
                "surface": "#282F29",
                "sidebar": definition["sidebar_dark"],
                "text": "#F1F5F1",
                "muted": "#B7C2B8",
                "border": "#39423A",
                "navigation": definition["sidebar_hover_dark"],
            }
        else:
            palette = {
                "canvas": "#F7FAF7",
                "content": "#F7FAF7",
                "surface": "#FFFFFF",
                "sidebar": definition["sidebar_light"],
                "text": "#1F2A22",
                "muted": "#5D6B60",
                "border": "#D9E5DB",
                "navigation": definition["sidebar_hover_light"],
            }

        accent = definition["accent"]
        accent_hover = definition["accent_hover"]
        accent_text = definition["accent_text"]

        self._preview_selection_label.setText(
            f"{definition['display_name']} · {MODE_DISPLAY_NAMES[selected_mode]}"
        )

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
                background: {accent};
                color: {accent_text};
                border-radius: 17px;
                font-weight: 700;
            }}

            QFrame#appearancePreviewNavItem {{
                background: {palette["navigation"]};
                border: none;
                border-radius: 4px;
            }}

            QWidget#appearancePreviewContent {{
                background: {palette["content"]};
                border-top-right-radius: 9px;
                border-bottom-right-radius: 9px;
            }}

            QLabel#appearancePreviewTitle {{
                color: {palette["text"]};
                font-size: 14pt;
                font-weight: 700;
            }}

            QLabel#appearancePreviewText {{
                color: {palette["muted"]};
            }}

            QFrame#appearancePreviewSurface {{
                background: {palette["surface"]};
                border: 1px solid {palette["border"]};
                border-radius: 8px;
            }}

            QLabel#appearancePreviewCardTitle {{
                color: {palette["text"]};
                font-weight: 700;
            }}

            QLabel#appearancePreviewCardText {{
                color: {palette["muted"]};
            }}

            QFrame#appearancePreviewAccent {{
                background: {accent};
                border: none;
                border-radius: 4px;
            }}

            QLabel#appearancePreviewAction {{
                background: {accent};
                color: {accent_text};
                border: 1px solid {accent_hover};
                border-radius: 6px;
                font-weight: 600;
            }}
            """
        )

    @staticmethod
    def _create_colour_icon(
        colour: str,
    ) -> QIcon:
        """Create a solid colour swatch icon."""

        pixmap = QPixmap(30, 30)
        pixmap.fill(QColor(colour))

        return QIcon(pixmap)

    @staticmethod
    def _create_divider() -> QFrame:
        """Create a horizontal divider."""

        divider = QFrame()
        divider.setObjectName("horizontalDivider")
        divider.setFrameShape(QFrame.Shape.HLine)

        return divider

    def _show_status(
        self,
        message: str,
        status: str,
    ) -> None:
        """Display appearance feedback."""

        self._status_label.setText(message)
        self._status_label.setProperty("status", status)
        self._status_label.setVisible(True)

        style = self._status_label.style()
        style.unpolish(self._status_label)
        style.polish(self._status_label)
