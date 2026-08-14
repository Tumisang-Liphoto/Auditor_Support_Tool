"""Build and restore multi-worksheet workbook packages."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.workbook_package import (
    DatasetType,
    FieldMappingStatus,
    MappingConfidence,
    PreparationStatus,
    PreparedColumn,
    WorkbookPackage,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_suggestion_service import (
    WorkbookSuggestionService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_import_service import (
    DataImportService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_service import (
    DataProfileService,
)

WORKBOOK_PACKAGE_SNAPSHOT_VERSION = 1


class WorkbookPackageRestoreError(RuntimeError):
    """Raised when saved workbook metadata cannot be applied safely."""


def new_dataset_id() -> str:
    """Return a new stable identifier for an imported worksheet dataset."""

    return f"dataset-{uuid4().hex}"


class WorkbookPackageService:
    """Inspect, load, profile, snapshot and restore workbook datasets."""

    def __init__(
        self,
        import_service: DataImportService | None = None,
        profile_service: DataProfileService | None = None,
        suggestion_service: WorkbookSuggestionService | None = None,
    ) -> None:
        self._import_service = import_service or DataImportService()
        self._profile_service = profile_service or DataProfileService()
        self._suggestion_service = suggestion_service or WorkbookSuggestionService()

    def build_package(
        self,
        source_path: str | Path,
        *,
        include_empty_worksheets: bool = False,
    ) -> WorkbookPackage:
        """Build a package containing every relevant worksheet."""

        source_info = self._import_service.inspect_source(source_path)

        package = WorkbookPackage(
            source_path=source_info.path,
            source_info=source_info,
        )

        for worksheet_info in source_info.worksheets:
            if not include_empty_worksheets and worksheet_info.estimated_data_rows == 0:
                continue

            table = self._import_service.load_table(
                source_info.path,
                worksheet_name=worksheet_info.name,
            )

            profile = self._profile_service.profile(table)

            (
                suggested_name,
                suggested_type,
                confidence,
            ) = self._suggestion_service.suggest_dataset(
                worksheet_info.name,
                table.headers,
            )

            columns = [self._prepare_column(column_profile) for column_profile in profile.columns]

            package.datasets.append(
                WorksheetDataset(
                    dataset_id=new_dataset_id(),
                    original_worksheet_name=worksheet_info.name,
                    suggested_display_name=suggested_name,
                    confirmed_display_name=suggested_name,
                    suggested_dataset_type=suggested_type,
                    confirmed_dataset_type=suggested_type,
                    suggestion_confidence=confidence,
                    status=PreparationStatus.NOT_REVIEWED,
                    selected=True,
                    loaded_table=table,
                    data_profile=profile,
                    columns=columns,
                )
            )

        return package

    def snapshot_package(
        self,
        package: WorkbookPackage,
    ) -> dict[str, object]:
        """Return serialisable metadata needed to reconstruct a package."""

        return {
            "snapshot_version": WORKBOOK_PACKAGE_SNAPSHOT_VERSION,
            "source_file_name": package.source_file_name,
            "datasets": [self._snapshot_dataset(dataset) for dataset in package.datasets],
        }

    def restore_package(
        self,
        source_path: str | Path,
        snapshot: dict[str, object],
    ) -> WorkbookPackage:
        """Reload source data and reapply saved stable IDs and decisions."""

        snapshot_version = self._require_int(
            snapshot,
            "snapshot_version",
        )

        if snapshot_version != WORKBOOK_PACKAGE_SNAPSHOT_VERSION:
            raise WorkbookPackageRestoreError(
                f"Unsupported workbook package snapshot version: {snapshot_version}."
            )

        raw_datasets = snapshot.get("datasets")

        if not isinstance(raw_datasets, list):
            raise WorkbookPackageRestoreError("Saved workbook package datasets must be an array.")

        package = self.build_package(source_path)

        rebuilt_by_worksheet = {
            dataset.original_worksheet_name: dataset for dataset in package.datasets
        }

        restored_datasets: list[WorksheetDataset] = []
        seen_dataset_ids: set[str] = set()

        for raw_dataset in raw_datasets:
            if not isinstance(raw_dataset, dict):
                raise WorkbookPackageRestoreError("Saved workbook datasets must be objects.")

            worksheet_name = self._require_string(
                raw_dataset,
                "original_worksheet_name",
            )
            rebuilt_dataset = rebuilt_by_worksheet.get(worksheet_name)

            if rebuilt_dataset is None:
                raise WorkbookPackageRestoreError(
                    "The saved worksheet could not be found in the "
                    f"workspace source file: {worksheet_name}"
                )

            self._restore_dataset(
                rebuilt_dataset,
                raw_dataset,
            )

            if rebuilt_dataset.dataset_id in seen_dataset_ids:
                raise WorkbookPackageRestoreError(
                    "Saved workbook package contains duplicate dataset IDs."
                )

            seen_dataset_ids.add(rebuilt_dataset.dataset_id)
            restored_datasets.append(rebuilt_dataset)

        package.datasets = restored_datasets

        return package

    def _snapshot_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> dict[str, object]:
        """Return saved metadata for one worksheet dataset."""

        return {
            "dataset_id": dataset.dataset_id,
            "original_worksheet_name": dataset.original_worksheet_name,
            "suggested_display_name": dataset.suggested_display_name,
            "confirmed_display_name": dataset.confirmed_display_name,
            "suggested_dataset_type": dataset.suggested_dataset_type.value,
            "confirmed_dataset_type": dataset.confirmed_dataset_type.value,
            "suggestion_confidence": dataset.suggestion_confidence.value,
            "status": dataset.status.value,
            "selected": dataset.selected,
            "preparation_status": dataset.preparation_status.value,
            "mapping_status": dataset.mapping_status.value,
            "field_mappings": dict(dataset.field_mappings),
            "columns": [self._snapshot_column(column) for column in dataset.columns],
        }

    @staticmethod
    def _snapshot_column(
        column: PreparedColumn,
    ) -> dict[str, object]:
        """Return saved metadata for one prepared column."""

        return {
            "column_id": column.column_id,
            "source_column": column.source_column,
            "position": column.position,
            "detected_type": column.detected_type.value,
            "suggested_name": column.suggested_name,
            "confirmed_name": column.confirmed_name,
            "suggested_type": column.suggested_type.value,
            "confirmed_type": column.confirmed_type.value,
            "suggestion_confidence": column.suggestion_confidence.value,
            "status": column.status.value,
            "included": column.included,
            "validation_warning": column.validation_warning,
        }

    def _restore_dataset(
        self,
        dataset: WorksheetDataset,
        raw_dataset: dict[str, object],
    ) -> None:
        """Apply saved metadata to one freshly rebuilt dataset."""

        dataset.dataset_id = self._require_string(
            raw_dataset,
            "dataset_id",
        )
        dataset.suggested_display_name = self._require_string(
            raw_dataset,
            "suggested_display_name",
        )
        dataset.confirmed_display_name = self._require_string(
            raw_dataset,
            "confirmed_display_name",
        )
        dataset.suggested_dataset_type = DatasetType(
            self._require_string(
                raw_dataset,
                "suggested_dataset_type",
            )
        )
        dataset.confirmed_dataset_type = DatasetType(
            self._require_string(
                raw_dataset,
                "confirmed_dataset_type",
            )
        )
        dataset.suggestion_confidence = MappingConfidence(
            self._require_string(
                raw_dataset,
                "suggestion_confidence",
            )
        )
        dataset.status = PreparationStatus(
            self._require_string(
                raw_dataset,
                "status",
            )
        )
        dataset.selected = self._require_bool(
            raw_dataset,
            "selected",
        )
        dataset.preparation_status = PreparationStatus(
            self._require_string(
                raw_dataset,
                "preparation_status",
            )
        )
        dataset.mapping_status = FieldMappingStatus(
            self._require_string(
                raw_dataset,
                "mapping_status",
            )
        )

        raw_columns = raw_dataset.get("columns")

        if not isinstance(raw_columns, list):
            raise WorkbookPackageRestoreError(
                f"Saved columns are invalid for '{dataset.original_worksheet_name}'."
            )

        rebuilt_by_identity = {
            (column.position, column.source_column): column for column in dataset.columns
        }

        restored_columns: list[PreparedColumn] = []
        seen_column_ids: set[str] = set()

        for raw_column in raw_columns:
            if not isinstance(raw_column, dict):
                raise WorkbookPackageRestoreError("Saved prepared columns must be objects.")

            position = self._require_int(
                raw_column,
                "position",
            )
            source_column = self._require_string(
                raw_column,
                "source_column",
            )
            column = rebuilt_by_identity.get((position, source_column))

            if column is None:
                raise WorkbookPackageRestoreError(
                    "A saved source column could not be found when "
                    f"restoring '{dataset.original_worksheet_name}': "
                    f"{source_column}"
                )

            self._restore_column(
                column,
                raw_column,
            )

            if column.column_id in seen_column_ids:
                raise WorkbookPackageRestoreError(
                    "Saved workbook package contains duplicate column IDs."
                )

            seen_column_ids.add(column.column_id)
            restored_columns.append(column)

        dataset.columns = restored_columns

        raw_mappings = raw_dataset.get(
            "field_mappings",
            {},
        )

        if not isinstance(raw_mappings, dict):
            raise WorkbookPackageRestoreError("Saved field mappings must be an object.")

        valid_column_ids = {column.column_id for column in dataset.columns}

        field_mappings: dict[str, str] = {}

        for raw_column_id, raw_field_key in raw_mappings.items():
            column_id = str(raw_column_id).strip()
            field_key = str(raw_field_key).strip()

            if column_id not in valid_column_ids:
                raise WorkbookPackageRestoreError(
                    f"A saved field mapping refers to an unknown column ID: {column_id}"
                )

            if field_key:
                field_mappings[column_id] = field_key

        dataset.field_mappings = field_mappings

    def _restore_column(
        self,
        column: PreparedColumn,
        raw_column: dict[str, object],
    ) -> None:
        """Apply saved preparation metadata to one rebuilt source column."""

        column.column_id = self._require_string(
            raw_column,
            "column_id",
        )
        column.detected_type = DetectedDataType(
            self._require_string(
                raw_column,
                "detected_type",
            )
        )
        column.suggested_name = self._require_string(
            raw_column,
            "suggested_name",
        )
        column.confirmed_name = self._require_string(
            raw_column,
            "confirmed_name",
        )
        column.suggested_type = DetectedDataType(
            self._require_string(
                raw_column,
                "suggested_type",
            )
        )
        column.confirmed_type = DetectedDataType(
            self._require_string(
                raw_column,
                "confirmed_type",
            )
        )
        column.suggestion_confidence = MappingConfidence(
            self._require_string(
                raw_column,
                "suggestion_confidence",
            )
        )
        column.status = PreparationStatus(
            self._require_string(
                raw_column,
                "status",
            )
        )
        column.included = self._require_bool(
            raw_column,
            "included",
        )
        column.validation_warning = str(
            raw_column.get(
                "validation_warning",
                "",
            )
        )

    def _prepare_column(
        self,
        column_profile,
    ) -> PreparedColumn:
        (
            suggested_name,
            confidence,
        ) = self._suggestion_service.suggest_column_name(column_profile)

        return PreparedColumn(
            source_column=column_profile.column_name,
            position=column_profile.position,
            detected_type=column_profile.detected_type,
            suggested_name=suggested_name,
            confirmed_name=suggested_name,
            suggested_type=column_profile.detected_type,
            confirmed_type=column_profile.detected_type,
            suggestion_confidence=confidence,
            status=PreparationStatus.NOT_REVIEWED,
        )

    @staticmethod
    def _require_string(
        source: dict[str, object],
        key: str,
    ) -> str:
        """Return a required non-blank string from saved metadata."""

        if key not in source:
            raise WorkbookPackageRestoreError(f"Saved workbook metadata is missing '{key}'.")

        value = str(source[key]).strip()

        if not value:
            raise WorkbookPackageRestoreError(f"Saved workbook metadata '{key}' cannot be blank.")

        return value

    @staticmethod
    def _require_int(
        source: dict[str, object],
        key: str,
    ) -> int:
        """Return a required integer from saved metadata."""

        if key not in source:
            raise WorkbookPackageRestoreError(f"Saved workbook metadata is missing '{key}'.")

        try:
            return int(source[key])
        except (TypeError, ValueError) as error:
            raise WorkbookPackageRestoreError(
                f"Saved workbook metadata '{key}' must be an integer."
            ) from error

    @staticmethod
    def _require_bool(
        source: dict[str, object],
        key: str,
    ) -> bool:
        """Return a required Boolean from saved metadata."""

        value = source.get(key)

        if not isinstance(value, bool):
            raise WorkbookPackageRestoreError(
                f"Saved workbook metadata '{key}' must be true or false."
            )

        return value
