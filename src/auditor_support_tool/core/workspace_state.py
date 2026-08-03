"""Shared in-memory state for the active audit workspace."""

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from auditor_support_tool.core.workbook_package import (
    WorkbookPackage,
    WorksheetDataset,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DataProfile,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
    SourceFileInfo,
)


class WorkspaceState(QObject):
    """Hold source data shared by the workspace pages."""

    source_changed = Signal()
    population_loaded = Signal()
    profile_created = Signal()

    workbook_package_changed = Signal()
    active_dataset_changed = Signal()

    workspace_cleared = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._source_path: Path | None = None
        self._source_info: SourceFileInfo | None = None

        self._workbook_package: WorkbookPackage | None = None
        self._active_dataset_id: str | None = None

        # Temporary compatibility properties for the existing pages.
        self._selected_worksheet: str | None = None
        self._loaded_table: LoadedTable | None = None
        self._data_profile: DataProfile | None = None

    @property
    def source_path(self) -> Path | None:
        """Return the active source-file path."""

        return self._source_path

    @property
    def source_info(self) -> SourceFileInfo | None:
        """Return metadata for the active source file."""

        return self._source_info

    @property
    def workbook_package(self) -> WorkbookPackage | None:
        """Return the complete loaded workbook package."""

        return self._workbook_package

    @property
    def active_dataset_id(self) -> str | None:
        """Return the identifier of the active worksheet dataset."""

        return self._active_dataset_id

    @property
    def active_dataset(self) -> WorksheetDataset | None:
        """Return the worksheet dataset currently being reviewed."""

        if self._workbook_package is None or self._active_dataset_id is None:
            return None

        return self._workbook_package.get_dataset(self._active_dataset_id)

    @property
    def datasets(self) -> tuple[WorksheetDataset, ...]:
        """Return all worksheet datasets in the package."""

        if self._workbook_package is None:
            return ()

        return tuple(self._workbook_package.datasets)

    @property
    def selected_datasets(self) -> tuple[WorksheetDataset, ...]:
        """Return worksheets selected for preparation."""

        if self._workbook_package is None:
            return ()

        return self._workbook_package.selected_datasets

    @property
    def selected_worksheet(self) -> str | None:
        """Return the active original worksheet name."""

        return self._selected_worksheet

    @property
    def loaded_table(self) -> LoadedTable | None:
        """Return the table belonging to the active dataset."""

        return self._loaded_table

    @property
    def data_profile(self) -> DataProfile | None:
        """Return the profile belonging to the active dataset."""

        return self._data_profile

    @property
    def has_source(self) -> bool:
        """Return whether a source file has been selected."""

        return self._source_info is not None

    @property
    def has_workbook_package(self) -> bool:
        """Return whether a complete workbook package is loaded."""

        return self._workbook_package is not None

    @property
    def has_active_dataset(self) -> bool:
        """Return whether a worksheet dataset is active."""

        return self.active_dataset is not None

    @property
    def has_loaded_population(self) -> bool:
        """Return whether the active dataset has a loaded table."""

        return self._loaded_table is not None

    @property
    def has_data_profile(self) -> bool:
        """Return whether the active dataset has a data profile."""

        return self._data_profile is not None

    def set_source(
        self,
        source_info: SourceFileInfo,
    ) -> None:
        """Register a source while clearing later-stage data."""

        self._source_path = source_info.path
        self._source_info = source_info

        self._workbook_package = None
        self._active_dataset_id = None

        self._selected_worksheet = None
        self._loaded_table = None
        self._data_profile = None

        self.source_changed.emit()

    def set_workbook_package(
        self,
        package: WorkbookPackage,
    ) -> None:
        """Store a complete workbook package."""

        self._source_path = package.source_path
        self._source_info = package.source_info
        self._workbook_package = package

        selected_datasets = package.selected_datasets

        if selected_datasets:
            self._set_active_dataset_values(selected_datasets[0])
        elif package.datasets:
            self._set_active_dataset_values(package.datasets[0])
        else:
            self._clear_active_dataset_values()

        self.source_changed.emit()
        self.workbook_package_changed.emit()

        if self.active_dataset is not None:
            self.active_dataset_changed.emit()
            self.population_loaded.emit()
            self.profile_created.emit()

    def set_active_dataset(
        self,
        dataset_id: str,
    ) -> None:
        """Make one worksheet dataset active for review."""

        if self._workbook_package is None:
            raise ValueError("No workbook package has been loaded.")

        dataset = self._workbook_package.get_dataset(dataset_id)

        if dataset is None:
            raise ValueError(f"Unknown dataset identifier: {dataset_id}")

        if dataset_id == self._active_dataset_id:
            return

        self._set_active_dataset_values(dataset)

        self.active_dataset_changed.emit()
        self.population_loaded.emit()
        self.profile_created.emit()

    def set_dataset_selected(
        self,
        dataset_id: str,
        selected: bool,
    ) -> None:
        """Include or exclude a worksheet from preparation."""

        dataset = self._require_dataset(dataset_id)
        dataset.selected = selected

        self.workbook_package_changed.emit()

    def set_loaded_table(
        self,
        loaded_table: LoadedTable,
    ) -> None:
        """Store a single table for compatibility with existing pages."""

        self._source_path = loaded_table.source_path
        self._selected_worksheet = loaded_table.worksheet_name
        self._loaded_table = loaded_table
        self._data_profile = None

        self.population_loaded.emit()

    def set_data_profile(
        self,
        data_profile: DataProfile,
    ) -> None:
        """Store a profile for the active dataset."""

        self._data_profile = data_profile

        active_dataset = self.active_dataset

        if active_dataset is not None:
            active_dataset.data_profile = data_profile

        self.profile_created.emit()

    def clear(self) -> None:
        """Clear all active workspace data."""

        self._source_path = None
        self._source_info = None

        self._workbook_package = None
        self._active_dataset_id = None

        self._selected_worksheet = None
        self._loaded_table = None
        self._data_profile = None

        self.workspace_cleared.emit()

    def _require_dataset(
        self,
        dataset_id: str,
    ) -> WorksheetDataset:
        """Return a dataset or raise a clear validation error."""

        if self._workbook_package is None:
            raise ValueError("No workbook package has been loaded.")

        dataset = self._workbook_package.get_dataset(dataset_id)

        if dataset is None:
            raise ValueError(f"Unknown dataset identifier: {dataset_id}")

        return dataset

    def _set_active_dataset_values(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        """Synchronise compatibility values with a dataset."""

        self._active_dataset_id = dataset.dataset_id
        self._selected_worksheet = dataset.original_worksheet_name
        self._loaded_table = dataset.loaded_table
        self._data_profile = dataset.data_profile

    def _clear_active_dataset_values(self) -> None:
        """Clear the active worksheet dataset."""

        self._active_dataset_id = None
        self._selected_worksheet = None
        self._loaded_table = None
        self._data_profile = None
