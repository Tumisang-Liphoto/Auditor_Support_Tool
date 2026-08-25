"""Tests for generic procedure-parameter validation and defaults."""

from __future__ import annotations

import pytest

from auditor_support_tool.core.procedure_definition import ProcedureDefinition
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
    ProcedureParameterType,
)
from auditor_support_tool.core.procedure_parameter_service import (
    ProcedureParameterValidationError,
    resolve_procedure_parameters,
)


def _definition() -> ProcedureDefinition:
    """Return a representative configurable generic procedure."""

    return ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        parameter_definitions=(
            ProcedureParameterDefinition.create(
                key="weekend_days",
                label="Weekend days",
                value_type=ProcedureParameterType.MULTI_CHOICE,
                required=True,
                default_value=("Saturday", "Sunday"),
                choices=("Saturday", "Sunday"),
            ),
            ProcedureParameterDefinition.create(
                key="high_value_threshold",
                label="High-value threshold",
                value_type=ProcedureParameterType.DECIMAL,
            ),
            ProcedureParameterDefinition.create(
                key="manual_journal_values",
                label="Manual-journal values",
                value_type=ProcedureParameterType.TEXT_LIST,
            ),
        ),
    )


def test_resolver_applies_defined_default_values() -> None:
    """Default values should become explicit reproducible run parameters."""

    assert resolve_procedure_parameters(_definition()) == {
        "weekend_days": [
            "Saturday",
            "Sunday",
        ]
    }


def test_resolver_normalises_decimal_and_text_list_values() -> None:
    """User input should become stable JSON-safe values before execution."""

    resolved = resolve_procedure_parameters(
        _definition(),
        {
            "high_value_threshold": " 100,000.00 ",
            "manual_journal_values": "Manual, Adjustment; Manual",
        },
    )

    assert resolved == {
        "weekend_days": [
            "Saturday",
            "Sunday",
        ],
        "high_value_threshold": "100000",
        "manual_journal_values": [
            "Manual",
            "Adjustment",
        ],
    }


def test_multi_choice_values_use_canonical_choice_labels() -> None:
    """Choice input should be matched case-insensitively and stored canonically."""

    resolved = resolve_procedure_parameters(
        _definition(),
        {
            "weekend_days": ["saturday"],
        },
    )

    assert resolved["weekend_days"] == ["Saturday"]


def test_required_multi_choice_cannot_be_empty() -> None:
    """A required selection must retain at least one configured value."""

    definition = _definition()
    weekend_definition = definition.parameter_definitions[0]

    without_default = ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        parameter_definitions=(
            ProcedureParameterDefinition.create(
                key=weekend_definition.key,
                label=weekend_definition.label,
                value_type=weekend_definition.value_type,
                required=True,
                choices=weekend_definition.choices,
            ),
        ),
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Weekend days is required",
    ):
        resolve_procedure_parameters(
            without_default,
            {"weekend_days": []},
        )


def test_invalid_decimal_is_rejected_before_execution() -> None:
    """Invalid numeric settings should fail with a direct user-facing message."""

    with pytest.raises(
        ProcedureParameterValidationError,
        match="High-value threshold must be a number",
    ):
        resolve_procedure_parameters(
            _definition(),
            {"high_value_threshold": "not-a-number"},
        )


def test_unknown_saved_parameter_is_rejected() -> None:
    """Stale or misspelled settings should not reach procedure logic silently."""

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Unknown procedure parameter",
    ):
        resolve_procedure_parameters(
            _definition(),
            {"unknown_setting": "value"},
        )


def test_untyped_legacy_procedure_parameters_remain_compatible() -> None:
    """Procedures not yet migrated to metadata should retain existing pass-through."""

    definition = ProcedureDefinition.create(
        procedure_id="GL006",
        name="Segregation of Duties",
        category="General Ledger",
    )

    assert resolve_procedure_parameters(
        definition,
        {"comparison_mode": "normalised"},
    ) == {"comparison_mode": "normalised"}
