"""Application theme management."""

from typing import TypedDict

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from auditor_support_tool.services.settings_service import (
    SUPPORTED_APPEARANCE_MODES,
    SUPPORTED_APPEARANCE_THEMES,
    AppearanceSettings,
    SettingsService,
)


class ThemeDefinition(TypedDict):
    """Colours and descriptive information for an application theme."""

    display_name: str
    description: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_text: str
    sidebar_light: str
    sidebar_dark: str
    sidebar_hover_light: str
    sidebar_hover_dark: str
    selected_light: str
    selected_dark: str


THEME_DEFINITIONS: dict[str, ThemeDefinition] = {
    "mint_green": {
        "display_name": "Mint Green",
        "description": "Calm and balanced",
        "accent": "#81D185",
        "accent_hover": "#6FC273",
        "accent_pressed": "#5EAE63",
        "accent_text": "#173A2C",
        "sidebar_light": "#173A2C",
        "sidebar_dark": "#10271E",
        "sidebar_hover_light": "#28503F",
        "sidebar_hover_dark": "#244638",
        "selected_light": "#EAF7EC",
        "selected_dark": "#203B2C",
    },
    "auditor_blue": {
        "display_name": "Auditor Blue",
        "description": "Formal and dependable",
        "accent": "#5B8DEF",
        "accent_hover": "#4A7FDD",
        "accent_pressed": "#3E6FC4",
        "accent_text": "#102A4C",
        "sidebar_light": "#17365D",
        "sidebar_dark": "#102540",
        "sidebar_hover_light": "#274E7D",
        "sidebar_hover_dark": "#1D3C63",
        "selected_light": "#EAF1FE",
        "selected_dark": "#1E3556",
    },
    "professional_teal": {
        "display_name": "Professional Teal",
        "description": "Modern and analytical",
        "accent": "#36B8A0",
        "accent_hover": "#2EA58F",
        "accent_pressed": "#278E7B",
        "accent_text": "#103B34",
        "sidebar_light": "#16453E",
        "sidebar_dark": "#102F2B",
        "sidebar_hover_light": "#24645A",
        "sidebar_hover_dark": "#1D4D46",
        "selected_light": "#E5F7F3",
        "selected_dark": "#1B3E39",
    },
    "royal_purple": {
        "display_name": "Royal Purple",
        "description": "Distinctive and polished",
        "accent": "#9B7AE5",
        "accent_hover": "#8967D4",
        "accent_pressed": "#7555BE",
        "accent_text": "#2F1D58",
        "sidebar_light": "#3D2F62",
        "sidebar_dark": "#29203F",
        "sidebar_hover_light": "#56427F",
        "sidebar_hover_dark": "#41335E",
        "selected_light": "#F1ECFC",
        "selected_dark": "#3A2E54",
    },
    "graphite": {
        "display_name": "Graphite",
        "description": "Neutral and understated",
        "accent": "#8A9AAA",
        "accent_hover": "#788897",
        "accent_pressed": "#677684",
        "accent_text": "#17202A",
        "sidebar_light": "#303A45",
        "sidebar_dark": "#20272F",
        "sidebar_hover_light": "#465360",
        "sidebar_hover_dark": "#343F49",
        "selected_light": "#EDF0F3",
        "selected_dark": "#343D46",
    },
}


THEME_DISPLAY_NAMES = {
    theme_key: definition["display_name"] for theme_key, definition in THEME_DEFINITIONS.items()
}


MODE_DISPLAY_NAMES = {
    "system": "System",
    "light": "Light",
    "dark": "Dark",
}


def get_theme_definition(theme: str) -> ThemeDefinition:
    """Return a validated application theme definition."""

    normalized_theme = theme.strip().lower()

    if normalized_theme not in SUPPORTED_APPEARANCE_THEMES:
        raise ValueError(f"Unsupported application theme: {theme}")

    definition = THEME_DEFINITIONS.get(normalized_theme)

    if definition is None:
        raise ValueError(f"No colour definition exists for theme: {theme}")

    return definition


def resolve_effective_mode(
    selected_mode: str,
    system_scheme: Qt.ColorScheme,
) -> str:
    """Resolve System mode to an effective light or dark mode."""

    normalized_mode = selected_mode.strip().lower()

    if normalized_mode == "system":
        if system_scheme == Qt.ColorScheme.Dark:
            return "dark"

        return "light"

    if normalized_mode not in {"light", "dark"}:
        raise ValueError("Appearance mode must be 'system', 'light' or 'dark'.")

    return normalized_mode


def build_stylesheet(
    theme: str,
    mode: str,
) -> str:
    """Build the application stylesheet for a theme and mode."""

    normalized_theme = theme.strip().lower()
    normalized_mode = mode.strip().lower()

    theme_definition = get_theme_definition(normalized_theme)

    if normalized_mode not in {"light", "dark"}:
        raise ValueError("Effective appearance mode must be 'light' or 'dark'.")

    accent = theme_definition["accent"]
    accent_hover = theme_definition["accent_hover"]
    accent_pressed = theme_definition["accent_pressed"]
    accent_text = theme_definition["accent_text"]

    if normalized_mode == "dark":
        colors = {
            "window": "#171C18",
            "content": "#202621",
            "surface": "#282F29",
            "sidebar": theme_definition["sidebar_dark"],
            "sidebar_hover": theme_definition["sidebar_hover_dark"],
            "sidebar_text": "#F0F3F1",
            "sidebar_muted": "#ADB7B0",
            "text": "#F1F5F1",
            "muted": "#B7C2B8",
            "border": "#39423A",
            "field": "#202621",
            "field_border": "#465047",
            "success": "#A7E4AD",
            "status": "#202621",
            "selected": theme_definition["selected_dark"],
            "error": "#FFB4AB",
        }
    else:
        colors = {
            "window": "#F7FAF7",
            "content": "#F7FAF7",
            "surface": "#FFFFFF",
            "sidebar": theme_definition["sidebar_light"],
            "sidebar_hover": theme_definition["sidebar_hover_light"],
            "sidebar_text": "#F4F7F5",
            "sidebar_muted": "#C0CBC4",
            "text": "#1F2A22",
            "muted": "#5D6B60",
            "border": "#D9E5DB",
            "field": "#FFFFFF",
            "field_border": "#C9D8CD",
            "success": "#2E6A45",
            "status": "#FFFFFF",
            "selected": theme_definition["selected_light"],
            "error": "#B42318",
        }

    return f"""
        QMainWindow {{
            background: {colors["window"]};
        }}

        QWidget {{
            color: {colors["text"]};
            font-family: "Segoe UI";
            font-size: 10pt;
        }}

        QFrame#sidebar {{
            background: {colors["sidebar"]};
            border: none;
        }}

        QLabel#applicationName {{
            color: #FFFFFF;
            font-size: 15pt;
            font-weight: 700;
        }}

        QLabel#applicationSubtitle {{
            color: {colors["sidebar_muted"]};
            font-size: 9pt;
        }}

        QPushButton#navigationButton,
        QToolButton#navigationGroupHeader {{
            background: transparent;
            color: {colors["sidebar_text"]};
            border: none;
            border-radius: 6px;
            padding: 10px 11px;
            text-align: left;
            font-weight: 600;
        }}

        QToolButton#navigationGroupHeader {{
            min-height: 22px;
        }}

        QPushButton#navigationButton:hover,
        QToolButton#navigationGroupHeader:hover {{
            background: {colors["sidebar_hover"]};
        }}

        QPushButton#navigationButton:checked {{
            background: {accent};
            color: {accent_text};
        }}

        QPushButton#navigationChildButton {{
            background: transparent;
            color: {colors["sidebar_text"]};
            border: none;
            border-radius: 5px;
            padding: 8px 10px;
            text-align: left;
            font-weight: 400;
        }}

        QPushButton#navigationChildButton:hover {{
            background: {colors["sidebar_hover"]};
            color: #FFFFFF;
        }}

        QPushButton#navigationChildButton:checked {{
            background: {colors["selected"]};
            color: {colors["text"]};
            border: 1px solid {accent};
            font-weight: 600;
        }}

        QLabel#sidebarVersion {{
            color: {colors["sidebar_muted"]};
            font-size: 9pt;
        }}

        QStackedWidget#pageStack,
        QWidget#dashboardPage,
        QWidget#pageContent {{
            background: {colors["content"]};
        }}

        QScrollArea#pageScrollArea {{
            background: {colors["content"]};
            border: none;
        }}

        QScrollArea#pageScrollArea > QWidget > QWidget {{
            background: {colors["content"]};
        }}

        QLabel#pageTitle {{
            color: {colors["text"]};
            font-size: 22pt;
            font-weight: 700;
        }}

        QLabel#pageSubtitle {{
            color: {colors["muted"]};
            font-size: 10pt;
        }}

        QFrame#card {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 10px;
        }}

        QLabel#cardTitle {{
            color: {colors["text"]};
            font-size: 13pt;
            font-weight: 700;
        }}

        QLabel#cardStatus {{
            color: {colors["success"]};
            font-size: 10pt;
            font-weight: 600;
        }}

        QLabel#cardText {{
            color: {colors["muted"]};
        }}

        QLineEdit#formInput,
        QComboBox#formInput {{
            background: {colors["field"]};
            color: {colors["text"]};
            border: 1px solid {colors["field_border"]};
            border-radius: 7px;
            padding: 7px 10px;
        }}

        QLineEdit#formInput:hover,
        QComboBox#formInput:hover {{
            border-color: {accent};
        }}

        QLineEdit#formInput:focus,
        QComboBox#formInput:focus {{
            border: 2px solid {accent};
        }}

        QLineEdit#formInput:disabled,
        QComboBox#formInput:disabled {{
            background: {colors["content"]};
            color: {colors["muted"]};
        }}

        QComboBox#formInput {{
            padding-right: 28px;
        }}

        QComboBox#formInput::drop-down {{
            border: none;
            width: 26px;
        }}

        QComboBox#formInput QAbstractItemView {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            outline: none;
            padding: 4px;
            selection-background-color: {accent};
            selection-color: {accent_text};
        }}

        QPushButton#primaryActionButton {{
            background: {accent};
            color: {accent_text};
            border: 1px solid {accent_hover};
            border-radius: 7px;
            padding: 9px 16px;
            min-height: 22px;
            font-weight: 600;
        }}

        QPushButton#primaryActionButton:hover {{
            background: {accent_hover};
        }}

        QPushButton#primaryActionButton:pressed {{
            background: {accent_pressed};
        }}

        QPushButton#primaryActionButton:disabled {{
            background: {colors["border"]};
            color: {colors["muted"]};
            border-color: {colors["border"]};
        }}

        QPushButton#secondaryActionButton,
        QPushButton#cardActionButton {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["field_border"]};
            border-radius: 7px;
            padding: 9px 14px;
            font-weight: 600;
        }}

        QPushButton#secondaryActionButton:hover,
        QPushButton#cardActionButton:hover {{
            background: {colors["selected"]};
            color: {colors["text"]};
            border-color: {accent};
        }}

        QFrame#settingsPanel {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 12px;
        }}

        QLabel#settingsEyebrow {{
            color: {accent};
            font-size: 8pt;
            font-weight: 700;
        }}

        QLabel#settingsPanelTitle {{
            color: {colors["text"]};
            font-size: 16pt;
            font-weight: 700;
        }}

        QLabel#settingsPanelDescription {{
            color: {colors["muted"]};
            font-size: 10pt;
        }}

        QLabel#settingsSectionTitle {{
            color: {colors["text"]};
            font-size: 11pt;
            font-weight: 700;
        }}

        QLabel#settingsSectionDescription {{
            color: {colors["muted"]};
        }}

        QLabel#fieldLabel {{
            color: {colors["text"]};
            font-weight: 600;
        }}

        QLabel#fieldHint {{
            color: {colors["muted"]};
            font-size: 9pt;
        }}

        QLabel#profileAvatar {{
            background: {colors["selected"]};
            color: {colors["text"]};
            border: 2px solid {accent};
            border-radius: 27px;
            font-size: 14pt;
            font-weight: 700;
        }}

        QLabel#privacyBadge,
        QLabel#selectedBadge {{
            background: {colors["selected"]};
            color: {colors["text"]};
            border: 1px solid {accent};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 8pt;
            font-weight: 700;
        }}

        QFrame#horizontalDivider {{
            background: {colors["border"]};
            border: none;
            min-height: 1px;
            max-height: 1px;
        }}

        QLabel#formStatus {{
            color: {colors["muted"]};
            font-weight: 600;
        }}

        QLabel#formStatus[status="success"] {{
            color: {colors["success"]};
        }}

        QLabel#formStatus[status="error"] {{
            color: {colors["error"]};
        }}

        QFrame#themeOption,
        QFrame#appearancePreviewPanel {{
            background: {colors["content"]};
            border: 1px solid {colors["border"]};
            border-radius: 9px;
        }}

        QFrame#themeSwatch {{
            background: {accent};
            border: 1px solid {accent_hover};
            border-radius: 9px;
        }}

        QLabel#themeName {{
            color: {colors["text"]};
            font-size: 11pt;
            font-weight: 700;
        }}

        QPushButton#themeChoiceButton {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["field_border"]};
            border-radius: 9px;
            padding: 12px 14px;
            min-height: 62px;
            text-align: left;
            font-weight: 600;
        }}

        QPushButton#themeChoiceButton:hover {{
            background: {colors["selected"]};
            border-color: {accent};
        }}

        QPushButton#themeChoiceButton:checked {{
            background: {colors["selected"]};
            border: 2px solid {accent};
        }}

        QPushButton#appearanceModeButton {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["field_border"]};
            border-radius: 8px;
            padding: 11px 12px;
            min-height: 48px;
            text-align: left;
            font-weight: 600;
        }}

        QPushButton#appearanceModeButton:hover {{
            background: {colors["selected"]};
            border-color: {accent};
        }}

        QPushButton#appearanceModeButton:checked {{
            background: {colors["selected"]};
            color: {colors["text"]};
            border: 2px solid {accent};
        }}

        QFrame#appearancePreviewCanvas {{
            border-radius: 9px;
        }}

        QFrame#profileSectionCard {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 11px;
        }}

        QLabel#profileSectionTitle {{
            color: {colors["text"]};
            font-size: 16pt;
            font-weight: 700;
        }}

        QLabel#profileSectionDescription {{
            color: {colors["muted"]};
            font-size: 10pt;
        }}

        QWidget#fieldLabelContainer,
        QWidget#formField {{
            background: transparent;
        }}

        QLabel#requiredAsterisk {{
            color: #D92D20;
            font-weight: 800;
            font-size: 11pt;
        }}

        QFrame#profileActionBar {{
            background: {colors["surface"]};
            border: 1px solid {colors["border"]};
            border-radius: 9px;
        }}

        QLineEdit#formInput[validationState="error"],
        QComboBox#formInput[validationState="error"] {{
            border: 2px solid {colors["error"]};
        }}

        QStatusBar {{
            background: {colors["status"]};
            color: {colors["muted"]};
            border-top: 1px solid {colors["border"]};
        }}

        QStatusBar::item {{
            border: none;
        }}

        QScrollBar:vertical {{
            background: {colors["content"]};
            width: 12px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background: {colors["field_border"]};
            border-radius: 5px;
            min-height: 30px;
        }}

        QScrollBar::handle:vertical:hover {{
            background: {colors["muted"]};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QToolTip {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            padding: 5px;
        }}
    """


class ThemeService(QObject):
    """Apply and persist application appearance settings."""

    appearance_changed = Signal(object)

    def __init__(
        self,
        application: QApplication,
        settings_service: SettingsService,
    ) -> None:
        super().__init__()

        self._application = application
        self._settings_service = settings_service

        self._application.styleHints().colorSchemeChanged.connect(
            self._handle_system_scheme_changed
        )

    def apply_saved_appearance(self) -> AppearanceSettings:
        """Apply the currently stored appearance."""

        appearance = self._settings_service.get_appearance()

        if (
            appearance.theme not in SUPPORTED_APPEARANCE_THEMES
            or appearance.mode not in SUPPORTED_APPEARANCE_MODES
        ):
            appearance = AppearanceSettings()

        self.apply_appearance(
            appearance,
            persist=False,
        )

        return appearance

    def apply_appearance(
        self,
        appearance: AppearanceSettings,
        *,
        persist: bool = True,
    ) -> None:
        """Apply an appearance and optionally save it."""

        theme = appearance.theme.strip().lower()
        selected_mode = appearance.mode.strip().lower()

        get_theme_definition(theme)

        if selected_mode not in SUPPORTED_APPEARANCE_MODES:
            raise ValueError("Appearance mode must be 'system', 'light' or 'dark'.")

        normalized_appearance = AppearanceSettings(
            theme=theme,
            mode=selected_mode,
        )

        system_scheme = self._application.styleHints().colorScheme()

        effective_mode = resolve_effective_mode(
            selected_mode=selected_mode,
            system_scheme=system_scheme,
        )

        stylesheet = build_stylesheet(
            theme=theme,
            mode=effective_mode,
        )

        self._application.setStyleSheet(stylesheet)

        if persist:
            self._settings_service.save_appearance(normalized_appearance)

        self.appearance_changed.emit(normalized_appearance)

    def _handle_system_scheme_changed(
        self,
        _scheme: Qt.ColorScheme,
    ) -> None:
        """Reapply the theme when Windows changes appearance."""

        appearance = self._settings_service.get_appearance()

        if appearance.mode == "system":
            self.apply_appearance(
                appearance,
                persist=False,
            )
