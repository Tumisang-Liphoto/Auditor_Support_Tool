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

        QPushButton#navigationButton {{
            background: transparent;
            color: #EAF7EC;
            border: none;
            border-radius: 6px;
            padding: 11px 12px;
            text-align: left;
            font-weight: 500;
        }}

        QPushButton#navigationButton:hover {{
            background: #28503F;
        }}

        QPushButton#navigationButton:pressed {{
            background: {PRIMARY_ACCENT};
            color: #173A2C;
        }}

        QLabel#sidebarVersion {{
            color: #B7C9BC;
            font-size: 9pt;
        }}

        QWidget#contentArea {{
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

        QLabel#cardText {{
            color: #5D6B60;
        }}

        QStatusBar {{
            background: #FFFFFF;
            color: #5D6B60;
            border-top: 1px solid #D9E5DB;
        }}
    """