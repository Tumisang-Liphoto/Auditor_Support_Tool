"""Manage preparation decisions for workbook worksheet datasets."""

from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
    PreparedColumn,
    WorksheetDataset,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DetectedDataType,
)


class DataPreparationError(ValueError):
    """Raised when a preparation change is invalid."""


class DataPreparationService:
    """Apply and validate editable dataset preparation decisions."""

    def update_column_name(
        self,
        dataset: WorksheetDataset,
        source_column: str,
        confirmed_name: str,
    ) -> PreparedColumn:
        """Change the prepared display name of a source column."""

        column = self._require_column(
            dataset,
            source_column,
        )

        cleaned_name = confirmed_name.strip()

        if not cleaned_name:
            raise DataPreparationError("A prepared column name cannot be blank.")

        duplicate_column = next(
            (
                existing
                for existing in dataset.columns
                if (
                    existing is not column
                    and existing.included
                    and existing.confirmed_name.casefold() == cleaned_name.casefold()
                )
            ),
            None,
        )

        if duplicate_column is not None:
            raise DataPreparationError(
                "Each included column must have a unique "
                f"prepared name. '{cleaned_name}' is already used."
            )

        column.confirmed_name = cleaned_name
        column.status = PreparationStatus.NOT_REVIEWED
        dataset.preparation_status = PreparationStatus.NOT_REVIEWED

        return column

    def update_column_type(
        self,
        dataset: WorksheetDataset,
        source_column: str,
        confirmed_type: DetectedDataType,
    ) -> PreparedColumn:
        """Change how a source column should be interpreted."""

        column = self._require_column(
            dataset,
            source_column,
        )

        column.confirmed_type = confirmed_type
        column.validation_warning = self._type_warning(column)

        column.status = (
            PreparationStatus.CONFIRMED_WITH_WARNINGS
            if column.validation_warning
            else PreparationStatus.NOT_REVIEWED
        )
        dataset.preparation_status = PreparationStatus.NOT_REVIEWED

        return column

    def set_column_included(
        self,
        dataset: WorksheetDataset,
        source_column: str,
        included: bool,
    ) -> PreparedColumn:
        """Include or exclude a source column from later processing."""

        column = self._require_column(
            dataset,
            source_column,
        )

        column.included = included
        column.status = PreparationStatus.NOT_REVIEWED if included else PreparationStatus.EXCLUDED
        dataset.preparation_status = PreparationStatus.NOT_REVIEWED

        return column

    def confirm_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> PreparationStatus:
        """Validate and confirm preparation of one dataset."""

        if not dataset.selected:
            dataset.preparation_status = PreparationStatus.EXCLUDED
            return dataset.preparation_status

        included_columns = dataset.included_columns

        if not included_columns:
            raise DataPreparationError(
                f"'{dataset.confirmed_display_name}' must contain at least one included column."
            )

        self._validate_unique_column_names(included_columns)

        warning_columns = tuple(column for column in included_columns if column.validation_warning)

        for column in dataset.columns:
            if not column.included:
                column.status = PreparationStatus.EXCLUDED
                continue

            column.status = (
                PreparationStatus.CONFIRMED_WITH_WARNINGS
                if column.validation_warning
                else PreparationStatus.CONFIRMED
            )

        dataset.preparation_status = (
            PreparationStatus.CONFIRMED_WITH_WARNINGS
            if warning_columns
            else PreparationStatus.CONFIRMED
        )

        return dataset.preparation_status

    def reset_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        """Restore all column preparation suggestions."""

        for column in dataset.columns:
            column.confirmed_name = column.suggested_name
            column.confirmed_type = column.suggested_type
            column.included = True
            column.validation_warning = ""
            column.status = PreparationStatus.NOT_REVIEWED

        dataset.preparation_status = PreparationStatus.NOT_REVIEWED

    @staticmethod
    def _validate_unique_column_names(
        columns: tuple[PreparedColumn, ...],
    ) -> None:
        names_seen: set[str] = set()

        for column in columns:
            cleaned_name = column.confirmed_name.strip()

            if not cleaned_name:
                raise DataPreparationError("Every included column must have a prepared name.")

            comparison_name = cleaned_name.casefold()

            if comparison_name in names_seen:
                raise DataPreparationError(
                    "Included columns must have unique "
                    f"prepared names. Duplicate: '{cleaned_name}'."
                )

            names_seen.add(comparison_name)

    @staticmethod
    def _type_warning(
        column: PreparedColumn,
    ) -> str:
        detected_type = column.detected_type
        confirmed_type = column.confirmed_type

        if confirmed_type == detected_type:
            return ""

        if confirmed_type == DetectedDataType.TEXT:
            return ""

        if detected_type == DetectedDataType.INTEGER and confirmed_type == DetectedDataType.DECIMAL:
            return ""

        if detected_type == DetectedDataType.DATE and confirmed_type == DetectedDataType.DATETIME:
            return ""

        if detected_type == DetectedDataType.BLANK:
            return (
                "The source column contains no populated values. "
                "The confirmed type cannot be validated."
            )

        if detected_type == DetectedDataType.MIXED:
            return (
                "The source column contains mixed value types. Conversion validation is required."
            )

        return (
            f"Detected as {detected_type.value.replace('_', ' ')} "
            f"but confirmed as "
            f"{confirmed_type.value.replace('_', ' ')}. "
            "Conversion validation is required."
        )

    @staticmethod
    def _require_column(
        dataset: WorksheetDataset,
        source_column: str,
    ) -> PreparedColumn:
        column = next(
            (existing for existing in dataset.columns if existing.source_column == source_column),
            None,
        )

        if column is None:
            raise DataPreparationError(
                f"Unknown source column '{source_column}' "
                f"in dataset '{dataset.confirmed_display_name}'."
            )

        return column
