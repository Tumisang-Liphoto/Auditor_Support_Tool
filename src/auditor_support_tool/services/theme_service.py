"""Application theme management."""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from auditor_support_tool.core.constants import PRIMARY_ACCENT
from auditor_support_tool.services.settings_service import (
    SUPPORTED_APPEARANCE_MODES,
    SUPPORTED_APPEARANCE_THEMES,
    AppearanceSettings,
    SettingsService,
)

THEME_DISPLAY_NAMES = {
    "mint_green": "Mint Green",
}

MODE_DISPLAY_NAMES = {
    "system": "System",
    "light": "Light",
    "dark": "Dark",
}


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

    if normalized_theme not in SUPPORTED_APPEARANCE_THEMES:
        raise ValueError(f"Unsupported application theme: {theme}")

    if normalized_mode not in {"light", "dark"}:
        raise ValueError("Effective appearance mode must be 'light' or 'dark'.")

    if normalized_mode == "dark":
        colors = {
            "window": "#171C18",
            "content": "#202621",
            "surface": "#282F29",
            "sidebar": "#10271E",
            "sidebar_hover": "#244638",
            "sidebar_text": "#EAF7EC",
            "sidebar_muted": "#A9B9AD",
            "text": "#F1F5F1",
            "muted": "#B7C2B8",
            "border": "#39423A",
            "field": "#202621",
            "field_border": "#465047",
            "success": "#A7E4AD",
            "status": "#202621",
        }
    else:
        colors = {
            "window": "#F7FAF7",
            "content": "#F7FAF7",
            "surface": "#FFFFFF",
            "sidebar": "#173A2C",
            "sidebar_hover": "#28503F",
            "sidebar_text": "#EAF7EC",
            "sidebar_muted": "#B7C9BC",
            "text": "#1F2A22",
            "muted": "#5D6B60",
            "border": "#D9E5DB",
            "field": "#FFFFFF",
            "field_border": "#C9D8CD",
            "success": "#2E6A45",
            "status": "#FFFFFF",
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
            background: {PRIMARY_ACCENT};
            color: #173A2C;
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
            background: #DDF2E0;
            color: #173A2C;
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
            padding: 8px 10px;
            min-height: 20px;
        }}

        QLineEdit#formInput:focus,
        QComboBox#formInput:focus {{
            border: 2px solid {PRIMARY_ACCENT};
        }}

        QComboBox#formInput QAbstractItemView {{
            background: {colors["surface"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            selection-background-color: {PRIMARY_ACCENT};
            selection-color: #173A2C;
        }}

        QPushButton#primaryActionButton {{
            background: {PRIMARY_ACCENT};
            color: #173A2C;
            border: 1px solid #6FC273;
            border-radius: 7px;
            padding: 9px 16px;
            font-weight: 600;
        }}

        QPushButton#primaryActionButton:hover {{
            background: #6FC273;
        }}

        QPushButton#primaryActionButton:pressed {{
            background: #5EAE63;
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
            background: #DDF2E0;
            color: #173A2C;
            border-color: {PRIMARY_ACCENT};
        }}

        QStatusBar {{
            background: {colors["status"]};
            color: {colors["muted"]};
            border-top: 1px solid {colors["border"]};
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

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
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

        if theme not in SUPPORTED_APPEARANCE_THEMES:
            raise ValueError(f"Unsupported application theme: {appearance.theme}")

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

        self._application.setStyleSheet(
            build_stylesheet(
                theme=theme,
                mode=effective_mode,
            )
        )

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
