"""Generic definition contract for audit procedures."""

from __future__ import annotations

from dataclasses import dataclass

from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
    procedure_display_id,
)
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
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

    audit_objective: str = ""
    isa_references: tuple[str, ...] = ()
    isa_basis_type: str = ""
    audit_rationale: str = ""
    result_meaning: str = ""
    limitations: tuple[str, ...] = ()

    required_fields: tuple[str, ...] = ()
    helpful_fields: tuple[str, ...] = ()
    dataset_requirements: tuple[ProcedureDatasetRequirement, ...] = ()
    parameter_definitions: tuple[ProcedureParameterDefinition, ...] = ()

    procedure_version: str = "1.0"

    @classmethod
    def create(
        cls,
        *,
        procedure_id: str,
        name: str,
        category: str,
        description: str = "",
        audit_objective: str = "",
        isa_references: tuple[str, ...] = (),
        isa_basis_type: str = "",
        audit_rationale: str = "",
        result_meaning: str = "",
        limitations: tuple[str, ...] = (),
        required_fields: tuple[str, ...] = (),
        helpful_fields: tuple[str, ...] = (),
        dataset_requirements: tuple[ProcedureDatasetRequirement, ...] = (),
        parameter_definitions: tuple[ProcedureParameterDefinition, ...] = (),
        procedure_version: str = "1.0",
    ) -> ProcedureDefinition:
        """Create and validate a generic procedure definition."""

        canonical_id = canonical_procedure_id(procedure_id)

        cleaned_name = name.strip()
        cleaned_category = category.strip()
        cleaned_description = description.strip()
        cleaned_audit_objective = audit_objective.strip()
        cleaned_isa_references = _normalise_text_items(
            isa_references,
            label="ISA reference",
        )
        cleaned_isa_basis_type = isa_basis_type.strip()
        cleaned_audit_rationale = audit_rationale.strip()
        cleaned_result_meaning = result_meaning.strip()
        cleaned_limitations = _normalise_text_items(
            limitations,
            label="Procedure limitation",
        )
        cleaned_version = procedure_version.strip()

        if not cleaned_name:
            raise ValueError("Procedure name is required.")

        if not cleaned_category:
            raise ValueError("Procedure category is required.")

        if not cleaned_version:
            raise ValueError("Procedure version is required.")

        methodology_values = (
            bool(cleaned_audit_objective),
            bool(cleaned_isa_references),
            bool(cleaned_isa_basis_type),
            bool(cleaned_audit_rationale),
            bool(cleaned_result_meaning),
            bool(cleaned_limitations),
        )

        if any(methodology_values) and not all(methodology_values):
            raise ValueError(
                "Procedure methodology metadata must be complete when any "
                "methodology field is provided."
            )

        cleaned_required_fields = _normalise_fields(
            required_fields,
            label="Required field",
        )

        cleaned_helpful_fields = _normalise_fields(
            helpful_fields,
            label="Helpful field",
        )

        cleaned_dataset_requirements = _normalise_dataset_requirements(dataset_requirements)
        cleaned_parameter_definitions = _normalise_parameter_definitions(parameter_definitions)

        if cleaned_dataset_requirements and (cleaned_required_fields or cleaned_helpful_fields):
            raise ValueError(
                "Dataset-aware procedures must declare fields inside "
                "dataset requirements rather than top-level field lists."
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
            audit_objective=cleaned_audit_objective,
            isa_references=cleaned_isa_references,
            isa_basis_type=cleaned_isa_basis_type,
            audit_rationale=cleaned_audit_rationale,
            result_meaning=cleaned_result_meaning,
            limitations=cleaned_limitations,
            required_fields=cleaned_required_fields,
            helpful_fields=cleaned_helpful_fields,
            dataset_requirements=cleaned_dataset_requirements,
            parameter_definitions=cleaned_parameter_definitions,
            procedure_version=cleaned_version,
        )

    @property
    def has_methodology_metadata(self) -> bool:
        """Return whether the complete methodology block is populated."""

        return bool(self.audit_objective)

    @property
    def display_id(self) -> str:
        """Return the user-facing procedure identifier."""

        return procedure_display_id(self.procedure_id)

    @property
    def all_fields(self) -> tuple[str, ...]:
        """Return all standard fields relevant to this procedure."""

        if not self.dataset_requirements:
            return self.required_fields + self.helpful_fields

        fields: list[str] = []
        seen: set[str] = set()

        for requirement in self.dataset_requirements:
            for field_key in requirement.all_fields:
                if field_key in seen:
                    continue

                seen.add(field_key)
                fields.append(field_key)

        return tuple(fields)

    @property
    def uses_dataset_requirements(self) -> bool:
        """Return whether the procedure uses dataset-aware requirements."""

        return bool(self.dataset_requirements)

    @property
    def is_multi_dataset(self) -> bool:
        """Return whether execution requires more than one dataset role."""

        return len(self.dataset_requirements) > 1

    @property
    def primary_dataset_requirement(
        self,
    ) -> ProcedureDatasetRequirement | None:
        """Return the primary dataset requirement when one is declared."""

        for requirement in self.dataset_requirements:
            if requirement.primary:
                return requirement

        return None

    @property
    def parameter_keys(self) -> tuple[str, ...]:
        """Return configurable parameter keys in definition order."""

        return tuple(definition.key for definition in self.parameter_definitions)


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


def _normalise_dataset_requirements(
    requirements: tuple[ProcedureDatasetRequirement, ...],
) -> tuple[ProcedureDatasetRequirement, ...]:
    """Validate dataset requirements and their stable role identifiers."""

    cleaned: list[ProcedureDatasetRequirement] = []
    seen_roles: set[str] = set()
    primary_count = 0

    for requirement in requirements:
        if not isinstance(requirement, ProcedureDatasetRequirement):
            raise TypeError("Dataset requirements must be ProcedureDatasetRequirement instances.")

        if requirement.role in seen_roles:
            raise ValueError(f"Dataset requirement role is duplicated: {requirement.role}.")

        seen_roles.add(requirement.role)
        cleaned.append(requirement)

        if requirement.primary:
            primary_count += 1

    if cleaned and primary_count != 1:
        raise ValueError(
            "Dataset-aware procedures must declare exactly one primary dataset requirement."
        )

    return tuple(cleaned)


def _normalise_parameter_definitions(
    definitions: tuple[ProcedureParameterDefinition, ...],
) -> tuple[ProcedureParameterDefinition, ...]:
    """Validate procedure parameter definitions and their unique keys."""

    cleaned: list[ProcedureParameterDefinition] = []
    seen_keys: set[str] = set()

    for definition in definitions:
        if not isinstance(definition, ProcedureParameterDefinition):
            raise TypeError(
                "Procedure parameter definitions must be ProcedureParameterDefinition instances."
            )

        if definition.key in seen_keys:
            raise ValueError(f"Procedure parameter is duplicated: {definition.key}.")

        seen_keys.add(definition.key)
        cleaned.append(definition)

    return tuple(cleaned)


def _normalise_text_items(
    values: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    """Validate and normalise ordered methodology text values."""

    cleaned_values: list[str] = []
    seen_values: set[str] = set()

    for raw_value in values:
        cleaned_value = str(raw_value).strip()

        if not cleaned_value:
            raise ValueError(f"{label} cannot be blank.")

        if cleaned_value in seen_values:
            raise ValueError(f"{label} is duplicated: {cleaned_value}.")

        seen_values.add(cleaned_value)
        cleaned_values.append(cleaned_value)

    return tuple(cleaned_values)
