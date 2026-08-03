"""Apply and validate source-to-standard field mappings."""

from auditor_support_tool.core.field_mapping_models import (
    StandardAuditField,
    fields_for_dataset_type,
)
from auditor_support_tool.core.workbook_package import (
    FieldMappingStatus,
    PreparationStatus,
    WorksheetDataset,
)


class FieldMappingError(ValueError):
    """Raised when a field-mapping operation is invalid."""


class FieldMappingService:
    """Manage field mappings for prepared worksheet datasets."""

    def available_fields(
        self,
        dataset: WorksheetDataset,
    ) -> tuple[StandardAuditField, ...]:
        """Return standard fields for the dataset's confirmed type."""

        return fields_for_dataset_type(dataset.confirmed_dataset_type)

    def assign_mapping(
        self,
        dataset: WorksheetDataset,
        source_column: str,
        standard_field_key: str,
    ) -> None:
        """Map an included source column to one standard field."""

        self._require_prepared_dataset(dataset)
        self._require_included_column(
            dataset,
            source_column,
        )

        cleaned_key = standard_field_key.strip()

        if not cleaned_key:
            self.remove_mapping(
                dataset,
                source_column,
            )
            return

        catalogue = self.available_fields(dataset)
        valid_keys = {field.key for field in catalogue}

        if cleaned_key not in valid_keys:
            raise FieldMappingError(
                
                    f"'{cleaned_key}' is not a recognised standard "
                    f"field for '{dataset.confirmed_display_name}'."
                
            )

        duplicate_source = next(
            (
                existing_source
                for existing_source, existing_key in dataset.field_mappings.items()
                if (existing_source != source_column and existing_key == cleaned_key)
            ),
            None,
        )

        if duplicate_source is not None:
            raise FieldMappingError(
                
                    f"'{cleaned_key}' is already mapped from "
                    f"'{duplicate_source}'. A standard field may "
                    "only be mapped once within a dataset."
                
            )

        dataset.field_mappings[source_column] = cleaned_key
        dataset.mapping_status = FieldMappingStatus.IN_PROGRESS

    def remove_mapping(
        self,
        dataset: WorksheetDataset,
        source_column: str,
    ) -> None:
        """Remove a mapping from one source column."""

        dataset.field_mappings.pop(
            source_column,
            None,
        )

        dataset.mapping_status = (
            FieldMappingStatus.IN_PROGRESS
            if dataset.field_mappings
            else FieldMappingStatus.NOT_STARTED
        )

    def confirm_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> FieldMappingStatus:
        """Validate and confirm mappings for one dataset."""

        self._require_prepared_dataset(dataset)

        catalogue = self.available_fields(dataset)

        if not catalogue:
            dataset.mapping_status = FieldMappingStatus.NOT_APPLICABLE
            return dataset.mapping_status

        self._remove_invalid_source_mappings(dataset)

        required_fields = {field.key for field in catalogue if field.required}
        mapped_fields = set(dataset.field_mappings.values())
        missing_required = required_fields - mapped_fields

        if missing_required:
            dataset.mapping_status = FieldMappingStatus.REVIEW_REQUIRED

            missing_labels = tuple(
                field.display_name for field in catalogue if field.key in missing_required
            )

            raise FieldMappingError(
                f"Required standard fields are not mapped: {', '.join(missing_labels)}."
            )

        dataset.mapping_status = FieldMappingStatus.CONFIRMED

        return dataset.mapping_status

    def reset_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        """Remove all mappings for one dataset."""

        dataset.field_mappings.clear()
        dataset.mapping_status = FieldMappingStatus.NOT_STARTED

    def missing_required_fields(
        self,
        dataset: WorksheetDataset,
    ) -> tuple[StandardAuditField, ...]:
        """Return required standard fields not yet mapped."""

        mapped_fields = set(dataset.field_mappings.values())

        return tuple(
            field
            for field in self.available_fields(dataset)
            if (field.required and field.key not in mapped_fields)
        )

    def mapped_field(
        self,
        dataset: WorksheetDataset,
        source_column: str,
    ) -> StandardAuditField | None:
        """Return the standard field mapped to a source column."""

        mapped_key = dataset.field_mappings.get(source_column)

        if mapped_key is None:
            return None

        return next(
            (field for field in self.available_fields(dataset) if field.key == mapped_key),
            None,
        )

    @staticmethod
    def _require_prepared_dataset(
        dataset: WorksheetDataset,
    ) -> None:
        if dataset.preparation_status not in {
            PreparationStatus.CONFIRMED,
            PreparationStatus.CONFIRMED_WITH_WARNINGS,
        }:
            raise FieldMappingError(
                
                    f"Complete Data Preparation for "
                    f"'{dataset.confirmed_display_name}' before "
                    "mapping fields."
                
            )

    @staticmethod
    def _require_included_column(
        dataset: WorksheetDataset,
        source_column: str,
    ) -> None:
        included_column = next(
            (
                column
                for column in dataset.columns
                if (column.source_column == source_column and column.included)
            ),
            None,
        )

        if included_column is None:
            raise FieldMappingError(
                
                    f"'{source_column}' is not an included prepared "
                    f"column in '{dataset.confirmed_display_name}'."
                
            )

    @staticmethod
    def _remove_invalid_source_mappings(
        dataset: WorksheetDataset,
    ) -> None:
        included_sources = set(dataset.included_source_columns)

        invalid_sources = tuple(
            source_column
            for source_column in dataset.field_mappings
            if source_column not in included_sources
        )

        for source_column in invalid_sources:
            dataset.field_mappings.pop(
                source_column,
                None,
            )
