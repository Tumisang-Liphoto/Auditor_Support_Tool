"""Shared in-memory state for the active audit workspace."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DataProfile,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
    SourceFileInfo,
)


class WorkspaceState(QObject):
    """Hold source-data state shared by workspace pages."""

    source_changed = Signal()
    population_loaded = Signal()
    profile_created = Signal()
    workspace_cleared = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._source_path: Path | None = None
        self._source_info: SourceFileInfo | None = None
        self._selected_worksheet: str | None = None
        self._loaded_table: LoadedTable | None = None
        self._data_profile: DataProfile | None = None

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
        """Return the population loaded for data preparation."""

        return self._loaded_table

    @property
    def data_profile(self) -> DataProfile | None:
        """Return the profile created for the loaded population."""

        return self._data_profile

    @property
    def has_source(self) -> bool:
        """Return whether a source file has been selected."""

        return self._source_info is not None

    @property
    def has_loaded_population(self) -> bool:
        """Return whether a population has been loaded."""

        return self._loaded_table is not None

    @property
    def has_data_profile(self) -> bool:
        """Return whether the loaded population has been profiled."""

        return self._data_profile is not None

    def set_source(
        self,
        source_info: SourceFileInfo,
    ) -> None:
        """Register a source file and clear later-stage data."""

        self._source_path = source_info.path
        self._source_info = source_info
        self._selected_worksheet = None
        self._loaded_table = None
        self._data_profile = None

        self.source_changed.emit()

    def set_loaded_table(
        self,
        loaded_table: LoadedTable,
    ) -> None:
        """Store the selected source population."""

        self._source_path = loaded_table.source_path
        self._selected_worksheet = loaded_table.worksheet_name
        self._loaded_table = loaded_table
        self._data_profile = None

        self.population_loaded.emit()

    def set_data_profile(
        self,
        data_profile: DataProfile,
    ) -> None:
        """Store the profile created for the loaded population."""

        self._data_profile = data_profile
        self.profile_created.emit()

    def clear(self) -> None:
        """Clear all active workspace source data."""

        self._source_path = None
        self._source_info = None
        self._selected_worksheet = None
        self._loaded_table = None
        self._data_profile = None

        self.workspace_cleared.emit()
