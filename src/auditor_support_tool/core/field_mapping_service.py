"""Apply, suggest and validate source-to-standard field mappings."""

import re
from difflib import SequenceMatcher

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
        return fields_for_dataset_type(dataset.confirmed_dataset_type)

    def suggest_mappings(
        self,
        dataset: WorksheetDataset,
        *,
        minimum_score: float = 0.45,
    ) -> dict[str, str]:
        """Apply unique closest-match suggestions to unmapped columns."""

        self._require_prepared_dataset(dataset)
        suggestions: dict[str, str] = {}
        used_keys = {key for key in dataset.field_mappings.values() if key}

        for column in dataset.included_columns:
            if dataset.field_mappings.get(column.source_column):
                continue

            candidates = tuple(
                field for field in self.available_fields(dataset) if field.key not in used_keys
            )
            if not candidates:
                break

            best_field = max(
                candidates,
                key=lambda field: self.match_score(
                    column.confirmed_name,
                    field,
                ),
            )
            score = self.match_score(
                column.confirmed_name,
                best_field,
            )
            if score < minimum_score:
                continue

            dataset.field_mappings[column.source_column] = best_field.key
            used_keys.add(best_field.key)
            suggestions[column.source_column] = best_field.key

        if suggestions:
            dataset.mapping_status = FieldMappingStatus.IN_PROGRESS

        return suggestions

    @classmethod
    def match_score(
        cls,
        prepared_name: str,
        field: StandardAuditField,
    ) -> float:
        prepared = cls._normalise(prepared_name)
        if not prepared:
            return 0.0

        candidates = (
            field.display_name,
            field.key,
            *field.aliases,
        )
        return max(
            cls._text_similarity(
                prepared,
                cls._normalise(candidate),
            )
            for candidate in candidates
            if candidate
        )

    def assign_mapping(
        self,
        dataset: WorksheetDataset,
        source_column: str,
        standard_field_key: str,
    ) -> None:
        self._require_prepared_dataset(dataset)
        self._require_included_column(dataset, source_column)

        cleaned_key = standard_field_key.strip()
        if not cleaned_key:
            self.remove_mapping(dataset, source_column)
            return

        valid_keys = {field.key for field in self.available_fields(dataset)}
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
        dataset.field_mappings.pop(source_column, None)
        dataset.mapping_status = (
            FieldMappingStatus.IN_PROGRESS
            if dataset.field_mappings
            else FieldMappingStatus.NOT_STARTED
        )

    def confirm_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> FieldMappingStatus:
        self._require_prepared_dataset(dataset)
        catalogue = self.available_fields(dataset)

        if not catalogue:
            dataset.mapping_status = FieldMappingStatus.NOT_APPLICABLE
            return dataset.mapping_status

        self._remove_invalid_source_mappings(dataset)

        dataset.mapping_status = FieldMappingStatus.CONFIRMED
        return dataset.mapping_status

    def reset_dataset(
        self,
        dataset: WorksheetDataset,
    ) -> None:
        dataset.field_mappings.clear()
        dataset.mapping_status = FieldMappingStatus.NOT_STARTED

    def missing_required_fields(
        self,
        dataset: WorksheetDataset,
    ) -> tuple[StandardAuditField, ...]:
        """Return no fields because mapping has no global requirements."""

        return ()

    def mapped_field(
        self,
        dataset: WorksheetDataset,
        source_column: str,
    ) -> StandardAuditField | None:
        mapped_key = dataset.field_mappings.get(source_column)
        if mapped_key is None:
            return None
        return next(
            (field for field in self.available_fields(dataset) if field.key == mapped_key),
            None,
        )

    @classmethod
    def _text_similarity(
        cls,
        left: str,
        right: str,
    ) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0

        left_tokens = set(left.split())
        right_tokens = set(right.split())
        token_score = (
            len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
            if left_tokens and right_tokens
            else 0.0
        )
        containment_score = (
            min(len(left), len(right)) / max(len(left), len(right))
            if left in right or right in left
            else 0.0
        )
        return max(
            SequenceMatcher(None, left, right).ratio(),
            token_score,
            containment_score,
        )

    @staticmethod
    def _normalise(value: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))

    @staticmethod
    def _require_prepared_dataset(
        dataset: WorksheetDataset,
    ) -> None:
        if dataset.preparation_status not in {
            PreparationStatus.CONFIRMED,
            PreparationStatus.CONFIRMED_WITH_WARNINGS,
        }:
            raise FieldMappingError(
                "Complete Data Preparation for "
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
            dataset.field_mappings.pop(source_column, None)
