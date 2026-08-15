"""Compact active-workspace summary for the application sidebar."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from auditor_support_tool.core.workspace_state import WorkspaceState


class WorkspaceContextPanel(QFrame):
    """Show concise information about the active audit workspace."""

    def __init__(
        self,
        *,
        workspace_state: WorkspaceState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._workspace_state = workspace_state

        self.setObjectName("workspaceContextPanel")

        self._build_interface()
        self._connect_signals()
        self._refresh()

    def _build_interface(self) -> None:
        """Build the compact workspace summary."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            12,
            11,
            12,
            11,
        )
        layout.setSpacing(5)

        eyebrow = QLabel("WORKSPACE")
        eyebrow.setObjectName("workspaceContextEyebrow")

        heading_layout = QHBoxLayout()
        heading_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        heading_layout.setSpacing(8)

        self._workspace_name = QLabel()
        self._workspace_name.setObjectName("workspaceContextName")
        self._workspace_name.setWordWrap(True)

        self._status_badge = QLabel("Active")
        self._status_badge.setObjectName("workspaceContextStatus")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading_layout.addWidget(
            self._workspace_name,
            1,
        )
        heading_layout.addWidget(
            self._status_badge,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        self._audit_year = QLabel()
        self._audit_year.setObjectName("workspaceContextDetail")

        self._period = QLabel()
        self._period.setObjectName("workspaceContextMuted")
        self._period.setWordWrap(True)

        layout.addWidget(eyebrow)
        layout.addLayout(heading_layout)
        layout.addWidget(self._audit_year)
        layout.addWidget(self._period)

    def _connect_signals(self) -> None:
        """Refresh when the active workspace changes."""

        self._workspace_state.workspace_identity_changed.connect(self._refresh)
        self._workspace_state.workspace_cleared.connect(self._refresh)

    def _refresh(self) -> None:
        """Refresh the displayed workspace context."""

        identity = self._workspace_state.workspace_identity

        if identity is None:
            self.setVisible(False)
            return

        self.setVisible(True)

        name = str(
            getattr(
                identity,
                "name",
                "",
            )
            or "Active Workspace"
        )

        audit_year = str(
            getattr(
                identity,
                "audit_year",
                "",
            )
            or ""
        )

        period_start = str(
            getattr(
                identity,
                "audit_period_start",
                "",
            )
            or ""
        )
        period_end = str(
            getattr(
                identity,
                "audit_period_end",
                "",
            )
            or ""
        )

        self._workspace_name.setText(name)

        self._audit_year.setText(
            self._audit_year_text(
                audit_year=audit_year,
                period_start=period_start,
                period_end=period_end,
            )
        )

        self._period.setText(
            self._period_text(
                period_start,
                period_end,
            )
        )

    @staticmethod
    def _audit_year_text(
        *,
        audit_year: str,
        period_start: str,
        period_end: str,
    ) -> str:
        """Return a concise audit-year description."""

        start = WorkspaceContextPanel._parse_date(period_start)
        end = WorkspaceContextPanel._parse_date(period_end)

        if start is not None and end is not None and start.year != end.year:
            return f"FY {start.year}/{str(end.year)[-2:]} Audit"

        if audit_year:
            return f"FY {audit_year} Audit"

        return "Audit workspace"

    @staticmethod
    def _period_text(
        period_start: str,
        period_end: str,
    ) -> str:
        """Return the formatted audit period."""

        start = WorkspaceContextPanel._parse_date(period_start)
        end = WorkspaceContextPanel._parse_date(period_end)

        if start is None or end is None:
            return "Audit period not specified"

        return f"{start:%d %b %Y} - {end:%d %b %Y}"

    @staticmethod
    def _parse_date(
        value: str,
    ) -> date | None:
        """Parse an ISO workspace date when available."""

        if not value:
            return None

        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
