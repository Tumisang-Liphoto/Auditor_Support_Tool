"""Generic dataset requirements declared by audit procedures."""

from __future__ import annotations

import re
from dataclasses import dataclass

from auditor_support_tool.core.workbook_package import DatasetType

_ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ProcedureDatasetRequirement:
    """One dataset role required by an audit procedure.

    The core model knows only generic dataset types, role identifiers and
    standard audit fields. Domain procedures decide which roles and dataset
    types they need.
    """

    role: str
    dataset_type: DatasetType
    required_fields: tuple[str, ...] = ()
    helpful_fields: tuple[str, ...] = ()
    primary: bool = False

    @classmethod
    def create(
        cls,
        *,
        role: str,
        dataset_type: DatasetType,
        required_fields: tuple[str, ...] = (),
        helpful_fields: tuple[str, ...] = (),
        primary: bool = False,
    ) -> ProcedureDatasetRequirement:
        """Create and validate one generic dataset requirement."""

        cleaned_role = role.strip().lower()

        if not cleaned_role:
            raise ValueError("Dataset requirement role is required.")

        if not _ROLE_PATTERN.fullmatch(cleaned_role):
            raise ValueError(
                "Dataset requirement role must use lowercase letters, "
                "numbers and underscores, beginning with a letter."
            )

        if not isinstance(dataset_type, DatasetType):
            raise TypeError("Dataset requirement type must be a DatasetType.")

        if dataset_type == DatasetType.UNCLASSIFIED:
            raise ValueError("A procedure cannot require an unclassified dataset type.")

        cleaned_required = _normalise_fields(
            required_fields,
            label="Required field",
        )
        cleaned_helpful = _normalise_fields(
            helpful_fields,
            label="Helpful field",
        )

        overlap = set(cleaned_required) & set(cleaned_helpful)

        if overlap:
            fields = ", ".join(sorted(overlap))
            raise ValueError(f"A dataset field cannot be both required and helpful: {fields}.")

        return cls(
            role=cleaned_role,
            dataset_type=dataset_type,
            required_fields=cleaned_required,
            helpful_fields=cleaned_helpful,
            primary=bool(primary),
        )

    @property
    def all_fields(self) -> tuple[str, ...]:
        """Return all fields relevant to this dataset role."""

        return self.required_fields + self.helpful_fields


def _normalise_fields(
    fields: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    """Validate and normalise standard audit-field keys."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for raw_field in fields:
        field_key = raw_field.strip()

        if not field_key:
            raise ValueError(f"{label} cannot be blank.")

        if field_key in seen:
            raise ValueError(f"{label} is duplicated: {field_key}.")

        seen.add(field_key)
        cleaned.append(field_key)

    return tuple(cleaned)
