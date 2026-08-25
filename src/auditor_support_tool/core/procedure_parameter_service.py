"""Validation and normalisation for generic procedure parameters."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation

from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
    ProcedureParameterType,
)

_LIST_SPLIT_PATTERN = re.compile(r"[,;\n]+")


class ProcedureParameterValidationError(ValueError):
    """Raised when procedure parameter values do not match their definitions."""


def resolve_procedure_parameters(
    definition: ProcedureDefinition,
    values: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return validated JSON-safe values including defined defaults."""

    supplied = dict(values or {})

    if not definition.parameter_definitions:
        return supplied

    known_keys = set(definition.parameter_keys)
    unknown_keys = sorted(set(supplied) - known_keys)

    if unknown_keys:
        raise ProcedureParameterValidationError(
            "Unknown procedure parameter(s): " + ", ".join(unknown_keys) + "."
        )

    resolved: dict[str, object] = {}

    for parameter in definition.parameter_definitions:
        has_supplied_value = parameter.key in supplied
        raw_value = supplied.get(parameter.key)

        if not has_supplied_value:
            raw_value = parameter.default_value

        if raw_value is None or _is_blank(raw_value):
            if parameter.required:
                raise ProcedureParameterValidationError(f"{parameter.label} is required.")

            continue

        normalised = normalise_procedure_parameter_value(
            parameter,
            raw_value,
        )

        if _is_blank(normalised):
            if parameter.required:
                raise ProcedureParameterValidationError(f"{parameter.label} is required.")

            continue

        resolved[parameter.key] = normalised

    return resolved


def normalise_procedure_parameter_value(
    definition: ProcedureParameterDefinition,
    value: object,
) -> object:
    """Normalise one parameter value according to generic metadata."""

    value_type = definition.value_type

    if value_type == ProcedureParameterType.TEXT:
        return _normalise_text(definition, value)

    if value_type == ProcedureParameterType.DECIMAL:
        return _normalise_decimal(definition, value)

    if value_type == ProcedureParameterType.INTEGER:
        return _normalise_integer(definition, value)

    if value_type == ProcedureParameterType.BOOLEAN:
        return _normalise_boolean(definition, value)

    if value_type == ProcedureParameterType.TEXT_LIST:
        return _normalise_text_list(definition, value)

    if value_type == ProcedureParameterType.CHOICE:
        return _normalise_choice(definition, value)

    if value_type == ProcedureParameterType.MULTI_CHOICE:
        return _normalise_multi_choice(definition, value)

    raise ProcedureParameterValidationError(
        f"Unsupported parameter type for {definition.label}: {value_type}."
    )


def format_procedure_parameter_value(
    definition: ProcedureParameterDefinition,
    value: object,
) -> str:
    """Return a concise user-facing representation of a parameter value."""

    if definition.value_type == ProcedureParameterType.BOOLEAN:
        return "Yes" if bool(value) else "No"

    if definition.value_type in {
        ProcedureParameterType.TEXT_LIST,
        ProcedureParameterType.MULTI_CHOICE,
    }:
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)

    return str(value)


def _normalise_text(
    definition: ProcedureParameterDefinition,
    value: object,
) -> str:
    text = str(value).strip()

    if not text:
        raise ProcedureParameterValidationError(f"{definition.label} cannot be blank.")

    return text


def _normalise_decimal(
    definition: ProcedureParameterDefinition,
    value: object,
) -> str:
    if isinstance(value, bool):
        raise ProcedureParameterValidationError(f"{definition.label} must be a number.")

    cleaned = str(value).strip().replace(",", "")

    try:
        decimal_value = Decimal(cleaned)
    except InvalidOperation as error:
        raise ProcedureParameterValidationError(f"{definition.label} must be a number.") from error

    if not decimal_value.is_finite():
        raise ProcedureParameterValidationError(f"{definition.label} must be a finite number.")

    canonical = format(decimal_value, "f")

    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")

    if canonical == "-0":
        canonical = "0"

    return canonical


def _normalise_integer(
    definition: ProcedureParameterDefinition,
    value: object,
) -> int:
    if isinstance(value, bool):
        raise ProcedureParameterValidationError(f"{definition.label} must be a whole number.")

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ProcedureParameterValidationError(f"{definition.label} must be a whole number.")

        return int(value)

    cleaned = str(value).strip().replace(",", "")

    try:
        return int(cleaned)
    except ValueError as error:
        raise ProcedureParameterValidationError(
            f"{definition.label} must be a whole number."
        ) from error


def _normalise_boolean(
    definition: ProcedureParameterDefinition,
    value: object,
) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    cleaned = str(value).strip().casefold()

    if cleaned in {"true", "yes", "1", "on"}:
        return True

    if cleaned in {"false", "no", "0", "off"}:
        return False

    raise ProcedureParameterValidationError(f"{definition.label} must be Yes or No.")


def _normalise_text_list(
    definition: ProcedureParameterDefinition,
    value: object,
) -> list[str]:
    candidates = _list_candidates(definition, value)
    return _clean_unique_text(candidates)


def _normalise_choice(
    definition: ProcedureParameterDefinition,
    value: object,
) -> str:
    cleaned = str(value).strip()

    for choice in definition.choices:
        if cleaned.casefold() == choice.casefold():
            return choice

    raise ProcedureParameterValidationError(
        f"{definition.label} must be one of: " + ", ".join(definition.choices) + "."
    )


def _normalise_multi_choice(
    definition: ProcedureParameterDefinition,
    value: object,
) -> list[str]:
    candidates = _list_candidates(definition, value)
    selected: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        cleaned = str(candidate).strip()

        if not cleaned:
            continue

        matched_choice = next(
            (choice for choice in definition.choices if cleaned.casefold() == choice.casefold()),
            None,
        )

        if matched_choice is None:
            raise ProcedureParameterValidationError(
                f"{definition.label} contains an unsupported value: {cleaned}."
            )

        identity = matched_choice.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        selected.append(matched_choice)

    return selected


def _list_candidates(
    definition: ProcedureParameterDefinition,
    value: object,
) -> list[object]:
    if isinstance(value, str):
        return [item for item in _LIST_SPLIT_PATTERN.split(value) if item.strip()]

    if isinstance(value, Mapping) or not isinstance(value, Iterable):
        raise ProcedureParameterValidationError(
            f"{definition.label} must contain one or more text values."
        )

    return list(value)


def _clean_unique_text(values: Iterable[object]) -> list[str]:
    cleaned_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = str(value).strip()

        if not cleaned:
            continue

        identity = cleaned.casefold()

        if identity in seen:
            continue

        seen.add(identity)
        cleaned_values.append(cleaned)

    return cleaned_values


def _is_blank(value: object) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, (list, tuple, set, frozenset)):
        return not value

    return False
