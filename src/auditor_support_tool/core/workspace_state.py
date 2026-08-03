"""Shared in-memory state for the active audit workspace."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
    SourceFileInfo,
)


class WorkspaceState(QObject):
    """Hold source-data state shared by workspace pages."""

    source_changed = Signal()
    population_loaded = Signal()
    workspace_cleared = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._source_path: Path | None = None
        self._source_info: SourceFileInfo | None = None
        self._selected_worksheet: str | None = None
        self._loaded_table: LoadedTable | None = None

    @property
    def source_path(self) -> Path | None:
        """Return the currently selected source-file path."""

        return self._source_path

    @property
    def source_info(self) -> SourceFileInfo | None:
        """Return metadata for the currently selected source file."""

        return self._source_info

    @property
    def selected_worksheet(self) -> str | None:
        """Return the currently selected worksheet name."""

        return self._selected_worksheet

    @property
    def loaded_table(self) -> LoadedTable | None:
        """Return the population loaded for audit testing."""

        return self._loaded_table

    @property
    def has_source(self) -> bool:
        """Return whether a source file has been selected."""

        return self._source_info is not None

    @property
    def has_loaded_population(self) -> bool:
        """Return whether a population has been loaded."""

        return self._loaded_table is not None

    def set_source(
        self,
        source_info: SourceFileInfo,
    ) -> None:
        """Register a source file and clear any prior loaded population."""

        self._source_path = source_info.path
        self._source_info = source_info
        self._selected_worksheet = None
        self._loaded_table = None

        self.source_changed.emit()

    def set_loaded_table(
        self,
        loaded_table: LoadedTable,
    ) -> None:
        """Store the selected and loaded source population."""

        self._source_path = loaded_table.source_path
        self._selected_worksheet = loaded_table.worksheet_name
        self._loaded_table = loaded_table

        self.population_loaded.emit()

    def clear(self) -> None:
        """Clear all active workspace source data."""

        self._source_path = None
        self._source_info = None
        self._selected_worksheet = None
        self._loaded_table = None

        self.workspace_cleared.emit()
