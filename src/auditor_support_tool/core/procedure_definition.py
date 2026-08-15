"""Generic definition contract for audit procedures."""

from __future__ import annotations

from dataclasses import dataclass

from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
    procedure_display_id,
)


@dataclass(frozen=True, slots=True)
class ProcedureDefinition:
    """Static definition of one audit procedure.

    This model describes what a procedure is and what standard audit fields
    it requires. It contains no procedure-specific execution logic.
    """

    procedure_id: str
    name: str
    category: str
    description: str = ""

    required_fields: tuple[str, ...] = ()
    helpful_fields: tuple[str, ...] = ()

    procedure_version: str = "1.0"

    @classmethod
    def create(
        cls,
        *,
        procedure_id: str,
        name: str,
        category: str,
        description: str = "",
        required_fields: tuple[str, ...] = (),
        helpful_fields: tuple[str, ...] = (),
        procedure_version: str = "1.0",
    ) -> ProcedureDefinition:
        """Create and validate a generic procedure definition."""

        canonical_id = canonical_procedure_id(procedure_id)

        cleaned_name = name.strip()
        cleaned_category = category.strip()
        cleaned_description = description.strip()
        cleaned_version = procedure_version.strip()

        if not cleaned_name:
            raise ValueError("Procedure name is required.")

        if not cleaned_category:
            raise ValueError("Procedure category is required.")

        if not cleaned_version:
            raise ValueError("Procedure version is required.")

        cleaned_required_fields = _normalise_fields(
            required_fields,
            label="Required field",
        )

        cleaned_helpful_fields = _normalise_fields(
            helpful_fields,
            label="Helpful field",
        )

        overlapping_fields = set(cleaned_required_fields) & set(cleaned_helpful_fields)

        if overlapping_fields:
            overlapping = ", ".join(sorted(overlapping_fields))

            raise ValueError(
                f"A standard field cannot be both required and helpful: {overlapping}."
            )

        return cls(
            procedure_id=canonical_id,
            name=cleaned_name,
            category=cleaned_category,
            description=cleaned_description,
            required_fields=cleaned_required_fields,
            helpful_fields=cleaned_helpful_fields,
            procedure_version=cleaned_version,
        )

    @property
    def display_id(self) -> str:
        """Return the user-facing procedure identifier."""

        return procedure_display_id(self.procedure_id)

    @property
    def all_fields(self) -> tuple[str, ...]:
        """Return all standard fields relevant to this procedure."""

        return self.required_fields + self.helpful_fields


def _normalise_fields(
    fields: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    """Validate and normalise standard audit-field keys."""

    cleaned_fields: list[str] = []
    seen_fields: set[str] = set()

    for raw_field in fields:
        cleaned_field = raw_field.strip()

        if not cleaned_field:
            raise ValueError(f"{label} cannot be blank.")

        if cleaned_field in seen_fields:
            raise ValueError(f"{label} is duplicated: {cleaned_field}.")

        seen_fields.add(cleaned_field)
        cleaned_fields.append(cleaned_field)

    return tuple(cleaned_fields)
