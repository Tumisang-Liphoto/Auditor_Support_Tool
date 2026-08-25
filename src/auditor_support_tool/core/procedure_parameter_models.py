"""Generic metadata for configurable audit-procedure parameters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_PARAMETER_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ProcedureParameterType(StrEnum):
    """Supported user-input types for procedure parameters."""

    TEXT = "text"
    DECIMAL = "decimal"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    TEXT_LIST = "text_list"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"


@dataclass(frozen=True, slots=True)
class ProcedureParameterDefinition:
    """Static definition of one configurable procedure parameter."""

    key: str
    label: str
    value_type: ProcedureParameterType
    description: str = ""
    required: bool = False
    default_value: object | None = None
    choices: tuple[str, ...] = ()
    placeholder: str = ""

    @classmethod
    def create(
        cls,
        *,
        key: str,
        label: str,
        value_type: ProcedureParameterType,
        description: str = "",
        required: bool = False,
        default_value: object | None = None,
        choices: tuple[str, ...] = (),
        placeholder: str = "",
    ) -> ProcedureParameterDefinition:
        """Create and validate generic procedure-parameter metadata."""

        cleaned_key = key.strip()
        cleaned_label = label.strip()
        cleaned_description = description.strip()
        cleaned_placeholder = placeholder.strip()

        if not _PARAMETER_KEY_PATTERN.fullmatch(cleaned_key):
            raise ValueError(
                "Procedure parameter keys must use lower-case letters, "
                "numbers and underscores and must begin with a letter."
            )

        if not cleaned_label:
            raise ValueError("Procedure parameter label is required.")

        if not isinstance(value_type, ProcedureParameterType):
            raise TypeError("Procedure parameter value_type must be a ProcedureParameterType.")

        cleaned_choices = _normalise_choices(choices)

        if value_type in {
            ProcedureParameterType.CHOICE,
            ProcedureParameterType.MULTI_CHOICE,
        }:
            if not cleaned_choices:
                raise ValueError("Choice procedure parameters must define at least one choice.")
        elif cleaned_choices:
            raise ValueError("Procedure parameter choices are only valid for choice parameters.")

        return cls(
            key=cleaned_key,
            label=cleaned_label,
            value_type=value_type,
            description=cleaned_description,
            required=bool(required),
            default_value=default_value,
            choices=cleaned_choices,
            placeholder=cleaned_placeholder,
        )


def _normalise_choices(
    choices: tuple[str, ...],
) -> tuple[str, ...]:
    """Return clean, case-insensitively unique parameter choices."""

    cleaned: list[str] = []
    seen: set[str] = set()

    for raw_choice in choices:
        choice = raw_choice.strip()

        if not choice:
            raise ValueError("Procedure parameter choices cannot be blank.")

        identity = choice.casefold()

        if identity in seen:
            raise ValueError(f"Procedure parameter choice is duplicated: {choice}.")

        seen.add(identity)
        cleaned.append(choice)

    return tuple(cleaned)
