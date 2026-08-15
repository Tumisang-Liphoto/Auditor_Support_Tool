"""Shared in-memory state for the active audit workspace."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from auditor_support_tool.core.data_models import (
    LoadedTable,
    SourceFileInfo,
)
from auditor_support_tool.core.data_profile_models import (
    DataProfile,
)
from auditor_support_tool.core.data_quality_models import DataQualityIssue
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)
from auditor_support_tool.core.workbook_package import (
    WorkbookPackage,
    WorksheetDataset,
)
from auditor_support_tool.core.workspace_models import (
    TransformationRecord,
    WorkspaceIdentity,
)


class WorkspaceState(QObject):
    """Hold shared state for the active audit workspace."""

    source_changed = Signal()
    population_loaded = Signal()
    profile_created = Signal()

    workbook_package_changed = Signal()
    active_dataset_changed = Signal()

    workspace_identity_changed = Signal()
    workspace_dirty_changed = Signal(bool)
    workspace_file_changed = Signal()

    transformation_history_changed = Signal()
    data_quality_issues_changed = Signal()
    procedure_parameters_changed = Signal(str)

    workspace_cleared = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._workspace_identity: WorkspaceIdentity | None = None
        self._workspace_file_path: Path | None = None
        self._is_dirty = False

        self._source_path: Path | None = None
        self._source_info: SourceFileInfo | None = None

        self._workbook_package: WorkbookPackage | None = None
        self._active_dataset_id: str | None = None

        self._transformation_history: list[TransformationRecord] = []
        self._data_quality_issues: list[DataQualityIssue] = []
        self._procedure_parameters: dict[str, dict[str, object]] = {}

        # Temporary compatibility properties for the existing pages.
        self._selected_worksheet: str | None = None
        self._loaded_table: LoadedTable | None = None
        self._data_profile: DataProfile | None = None

    @property
    def workspace_identity(self) -> WorkspaceIdentity | None:
        """Return the active workspace identity."""

        return self._workspace_identity

    @property
    def workspace_file_path(self) -> Path | None:
        """Return the saved workspace-document path."""

        return self._workspace_file_path

    @property
    def has_workspace(self) -> bool:
        """Return whether an audit workspace has been created or opened."""

        return self._workspace_identity is not None

    @property
    def is_dirty(self) -> bool:
        """Return whether the workspace contains unsaved changes."""

        return self._is_dirty

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
    def transformation_history(self) -> tuple[TransformationRecord, ...]:
        """Return the workspace transformation history in recorded order."""

        return tuple(self._transformation_history)

    @property
    def data_quality_issues(self) -> tuple[DataQualityIssue, ...]:
        """Return all data-quality issues recorded for the active workspace."""

        return tuple(self._data_quality_issues)

    @property
    def blocking_data_quality_issues(self) -> tuple[DataQualityIssue, ...]:
        """Return data-quality issues that should block affected execution."""

        return tuple(issue for issue in self._data_quality_issues if issue.blocks_execution)

    def data_quality_issues_for_dataset(
        self,
        dataset_id: str,
    ) -> tuple[DataQualityIssue, ...]:
        """Return data-quality issues belonging to one dataset."""

        return tuple(issue for issue in self._data_quality_issues if issue.dataset_id == dataset_id)

    @property
    def procedure_parameters(self) -> dict[str, dict[str, object]]:
        """Return a defensive copy of saved parameters for all procedures."""

        return deepcopy(self._procedure_parameters)

    def get_procedure_parameters(
        self,
        procedure_id: str,
    ) -> dict[str, object]:
        """Return saved parameters for one procedure."""

        canonical_id = canonical_procedure_id(procedure_id)

        return deepcopy(
            self._procedure_parameters.get(
                canonical_id,
                {},
            )
        )

    def set_procedure_parameters(
        self,
        procedure_id: str,
        parameters: Mapping[str, object],
        *,
        mark_dirty: bool = True,
    ) -> None:
        """Store serialisable parameters for one audit procedure."""

        if self._workspace_identity is None:
            raise ValueError(
                "An active audit workspace is required before saving procedure parameters."
            )

        canonical_id = canonical_procedure_id(procedure_id)
        cleaned_parameters = _normalise_procedure_parameter_values(parameters)

        current = self._procedure_parameters.get(
            canonical_id,
            {},
        )

        if current == cleaned_parameters:
            return

        if cleaned_parameters:
            self._procedure_parameters[canonical_id] = cleaned_parameters
        else:
            self._procedure_parameters.pop(
                canonical_id,
                None,
            )

        self.procedure_parameters_changed.emit(canonical_id)

        if mark_dirty:
            self.mark_dirty()

    def set_all_procedure_parameters(
        self,
        procedure_parameters: Mapping[str, Mapping[str, object]],
        *,
        mark_dirty: bool = True,
    ) -> None:
        """Replace the complete saved procedure-parameter store."""

        if self._workspace_identity is None:
            raise ValueError(
                "An active audit workspace is required before restoring procedure parameters."
            )

        cleaned_store: dict[str, dict[str, object]] = {}

        for procedure_id, parameters in procedure_parameters.items():
            canonical_id = canonical_procedure_id(str(procedure_id))
            cleaned = _normalise_procedure_parameter_values(parameters)

            if cleaned:
                cleaned_store[canonical_id] = cleaned

        if cleaned_store == self._procedure_parameters:
            return

        previous_ids = set(self._procedure_parameters)
        new_ids = set(cleaned_store)

        self._procedure_parameters = cleaned_store

        for procedure_id in sorted(previous_ids | new_ids):
            self.procedure_parameters_changed.emit(procedure_id)

        if mark_dirty:
            self.mark_dirty()

    def clear_procedure_parameters(
        self,
        procedure_id: str,
    ) -> None:
        """Remove saved parameters for one procedure."""

        self.set_procedure_parameters(
            procedure_id,
            {},
        )

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

    def start_workspace(
        self,
        identity: WorkspaceIdentity,
        *,
        file_path: Path | None = None,
    ) -> None:
        """Start a newly created or previously loaded audit workspace."""

        self.clear()

        self._workspace_identity = identity
        self._workspace_file_path = (
            file_path.expanduser().resolve() if file_path is not None else None
        )

        self._set_dirty(file_path is None)

        self.workspace_identity_changed.emit()
        self.workspace_file_changed.emit()

    def set_workspace_file_path(
        self,
        file_path: Path | None,
    ) -> None:
        """Set the persistent workspace-document path."""

        resolved_path = file_path.expanduser().resolve() if file_path is not None else None

        if resolved_path == self._workspace_file_path:
            return

        self._workspace_file_path = resolved_path
        self.workspace_file_changed.emit()

    def mark_dirty(self) -> None:
        """Mark the active workspace as containing unsaved changes."""

        if self._workspace_identity is None:
            return

        self._workspace_identity.touch()
        self._set_dirty(True)

    def mark_saved(self) -> None:
        """Mark the active workspace as fully saved."""

        self._set_dirty(False)

    def record_transformation(
        self,
        *,
        action: str,
        dataset_id: str | None = None,
        column_id: str | None = None,
        source_column: str | None = None,
        old_value: object | None = None,
        new_value: object | None = None,
        details: dict[str, object] | None = None,
    ) -> TransformationRecord:
        """Record one auditable workspace transformation."""

        if self._workspace_identity is None:
            raise ValueError(
                "An active audit workspace is required before recording transformation history."
            )

        record = TransformationRecord.create(
            action=action,
            dataset_id=dataset_id,
            column_id=column_id,
            source_column=source_column,
            old_value=old_value,
            new_value=new_value,
            details=details,
        )

        self._transformation_history.append(record)
        self.transformation_history_changed.emit()
        self.mark_dirty()

        return record

    def set_transformation_history(
        self,
        records: tuple[TransformationRecord, ...] | list[TransformationRecord],
        *,
        mark_dirty: bool = False,
    ) -> None:
        """Replace transformation history, primarily when loading a workspace."""

        self._transformation_history = list(records)
        self.transformation_history_changed.emit()

        if mark_dirty:
            self.mark_dirty()

    def add_data_quality_issue(
        self,
        issue: DataQualityIssue,
    ) -> None:
        """Add one data-quality issue to the active workspace."""

        if self._workspace_identity is None:
            raise ValueError(
                "An active audit workspace is required before recording data-quality issues."
            )

        if any(existing.issue_id == issue.issue_id for existing in self._data_quality_issues):
            return

        self._data_quality_issues.append(issue)
        self.data_quality_issues_changed.emit()
        self.mark_dirty()

    def set_data_quality_issues(
        self,
        issues: tuple[DataQualityIssue, ...] | list[DataQualityIssue],
        *,
        mark_dirty: bool = False,
    ) -> None:
        """Replace data-quality issues, primarily when loading a workspace."""

        self._data_quality_issues = list(issues)
        self.data_quality_issues_changed.emit()

        if mark_dirty:
            self.mark_dirty()

    def clear_data_quality_issues(
        self,
        *,
        dataset_id: str | None = None,
    ) -> None:
        """Clear all issues or only issues belonging to one dataset."""

        if dataset_id is None:
            changed = bool(self._data_quality_issues)
            self._data_quality_issues = []
        else:
            remaining = [
                issue for issue in self._data_quality_issues if issue.dataset_id != dataset_id
            ]
            changed = len(remaining) != len(self._data_quality_issues)
            self._data_quality_issues = remaining

        if not changed:
            return

        self.data_quality_issues_changed.emit()
        self.mark_dirty()

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
        self.mark_dirty()

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

        self.mark_dirty()

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

        self.mark_dirty()

    def set_dataset_selected(
        self,
        dataset_id: str,
        selected: bool,
    ) -> None:
        """Include or exclude a worksheet from preparation."""

        dataset = self._require_dataset(dataset_id)

        if dataset.selected == selected:
            return

        dataset.selected = selected

        self.workbook_package_changed.emit()
        self.mark_dirty()

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
        self.mark_dirty()

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
        self.mark_dirty()

    def clear(self) -> None:
        """Clear all active workspace data."""

        had_identity = self._workspace_identity is not None
        had_file_path = self._workspace_file_path is not None
        was_dirty = self._is_dirty

        self._workspace_identity = None
        self._workspace_file_path = None
        self._is_dirty = False

        self._source_path = None
        self._source_info = None

        self._workbook_package = None
        self._active_dataset_id = None

        had_transformation_history = bool(self._transformation_history)
        self._transformation_history = []

        had_data_quality_issues = bool(self._data_quality_issues)
        self._data_quality_issues = []

        procedure_parameter_ids = tuple(self._procedure_parameters)
        self._procedure_parameters = {}

        self._selected_worksheet = None
        self._loaded_table = None
        self._data_profile = None

        if had_identity:
            self.workspace_identity_changed.emit()

        if had_file_path:
            self.workspace_file_changed.emit()

        if was_dirty:
            self.workspace_dirty_changed.emit(False)

        if had_transformation_history:
            self.transformation_history_changed.emit()

        if had_data_quality_issues:
            self.data_quality_issues_changed.emit()

        for procedure_id in procedure_parameter_ids:
            self.procedure_parameters_changed.emit(procedure_id)

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

    def _set_dirty(
        self,
        dirty: bool,
    ) -> None:
        """Update and announce the workspace dirty state."""

        if self._is_dirty == dirty:
            return

        self._is_dirty = dirty
        self.workspace_dirty_changed.emit(dirty)


def _normalise_procedure_parameter_values(
    parameters: Mapping[str, object],
) -> dict[str, object]:
    """Return a JSON-safe copy of one procedure's parameter values."""

    if not isinstance(parameters, Mapping):
        raise TypeError("Procedure parameters must be a mapping.")

    cleaned: dict[str, object] = {}

    for raw_key, raw_value in parameters.items():
        key = str(raw_key).strip()

        if not key:
            raise ValueError("Procedure parameter keys cannot be blank.")

        cleaned[key] = _normalise_parameter_value(
            raw_value,
            path=key,
        )

    return cleaned


def _normalise_parameter_value(
    value: object,
    *,
    path: str,
) -> object:
    """Normalise one value to JSON-compatible workspace data."""

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _normalise_parameter_value(
                item,
                path=f"{path}[]",
            )
            for item in value
        ]

    if isinstance(value, Mapping):
        normalised: dict[str, object] = {}

        for raw_key, nested_value in value.items():
            nested_key = str(raw_key).strip()

            if not nested_key:
                raise ValueError("Nested procedure parameter keys cannot be blank.")

            normalised[nested_key] = _normalise_parameter_value(
                nested_value,
                path=f"{path}.{nested_key}",
            )

        return normalised

    raise TypeError(
        "Procedure parameter values must be JSON-compatible. "
        f"Unsupported value at {path}: "
        f"{type(value).__name__}."
    )
