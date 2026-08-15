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


@dataclass(frozen=True, slots=True)
class ProcedureParameterDefinition:
    """Static definition of one configurable procedure parameter."""

    key: str
    label: str
    value_type: ProcedureParameterType
    description: str = ""
    required: bool = False

    @classmethod
    def create(
        cls,
        *,
        key: str,
        label: str,
        value_type: ProcedureParameterType,
        description: str = "",
        required: bool = False,
    ) -> ProcedureParameterDefinition:
        """Create and validate generic procedure-parameter metadata."""

        cleaned_key = key.strip()
        cleaned_label = label.strip()
        cleaned_description = description.strip()

        if not _PARAMETER_KEY_PATTERN.fullmatch(cleaned_key):
            raise ValueError(
                "Procedure parameter keys must use lower-case letters, "
                "numbers and underscores and must begin with a letter."
            )

        if not cleaned_label:
            raise ValueError("Procedure parameter label is required.")

        if not isinstance(value_type, ProcedureParameterType):
            raise TypeError("Procedure parameter value_type must be a ProcedureParameterType.")

        return cls(
            key=cleaned_key,
            label=cleaned_label,
            value_type=value_type,
            description=cleaned_description,
            required=bool(required),
        )
