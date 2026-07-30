"""Application theme definitions."""

from auditor_support_tool.core.constants import PRIMARY_ACCENT


def build_default_stylesheet() -> str:
    """Return the initial Mint Green application stylesheet."""

    return f"""
        QMainWindow {{
            background: #F7FAF7;
        }}

        QWidget {{
            color: #1F2A22;
            font-family: "Segoe UI";
            font-size: 10pt;
        }}

        QFrame#sidebar {{
            background: #173A2C;
            border: none;
        }}

        QLabel#applicationName {{
            color: #FFFFFF;
            font-size: 15pt;
            font-weight: 700;
        }}

        QLabel#applicationSubtitle {{
            color: #B7C9BC;
            font-size: 9pt;
        }}

        QPushButton#navigationButton,
        QToolButton#navigationGroupHeader {{
            background: transparent;
            color: #EAF7EC;
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
            background: #28503F;
        }}

        QPushButton#navigationButton:checked {{
            background: {PRIMARY_ACCENT};
            color: #173A2C;
        }}

        QPushButton#navigationChildButton {{
            background: transparent;
            color: #DCEADF;
            border: none;
            border-radius: 5px;
            padding: 8px 10px;
            text-align: left;
            font-weight: 400;
        }}

        QPushButton#navigationChildButton:hover {{
            background: #28503F;
            color: #FFFFFF;
        }}

        QPushButton#navigationChildButton:checked {{
            background: #DDF2E0;
            color: #173A2C;
            font-weight: 600;
        }}

        QLabel#sidebarVersion {{
            color: #B7C9BC;
            font-size: 9pt;
        }}

        QStackedWidget#pageStack,
        QWidget#dashboardPage,
        QWidget#pageContent {{
            background: #F7FAF7;
        }}

        QScrollArea#pageScrollArea {{
            background: #F7FAF7;
            border: none;
        }}

        QScrollArea#pageScrollArea > QWidget > QWidget {{
            background: #F7FAF7;
        }}

        QLabel#pageTitle {{
            color: #173A2C;
            font-size: 22pt;
            font-weight: 700;
        }}

        QLabel#pageSubtitle {{
            color: #5D6B60;
            font-size: 10pt;
        }}

        QFrame#card {{
            background: #FFFFFF;
            border: 1px solid #D9E5DB;
            border-radius: 10px;
        }}

        QLabel#cardTitle {{
            color: #173A2C;
            font-size: 13pt;
            font-weight: 700;
        }}

        QLabel#cardStatus {{
            color: #2E6A45;
            font-size: 10pt;
            font-weight: 600;
        }}

        QLabel#cardText {{
            color: #5D6B60;
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
            background: #FFFFFF;
            color: #24543C;
            border: 1px solid #C9D8CD;
            border-radius: 7px;
            padding: 9px 14px;
            font-weight: 600;
        }}

        QPushButton#secondaryActionButton:hover,
        QPushButton#cardActionButton:hover {{
            background: #EAF7EC;
            border-color: #81D185;
        }}

        QStatusBar {{
            background: #FFFFFF;
            color: #5D6B60;
            border-top: 1px solid #D9E5DB;
        }}
    """
