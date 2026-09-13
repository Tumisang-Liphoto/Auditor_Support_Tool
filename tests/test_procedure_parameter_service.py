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
    format_procedure_parameter_value,
    normalise_procedure_parameter_value,
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

def test_text_parameter_is_trimmed() -> None:
    """Text parameters should be stored without surrounding whitespace."""

    parameter = ProcedureParameterDefinition.create(
        key="description",
        label="Description",
        value_type=ProcedureParameterType.TEXT,
    )

    assert (
        normalise_procedure_parameter_value(
            parameter,
            "  Manual journal  ",
        )
        == "Manual journal"
    )


def test_decimal_rejects_boolean_and_non_finite_values() -> None:
    """Boolean and non-finite values must not become audit thresholds."""

    parameter = ProcedureParameterDefinition.create(
        key="threshold",
        label="Threshold",
        value_type=ProcedureParameterType.DECIMAL,
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Threshold must be a number",
    ):
        normalise_procedure_parameter_value(
            parameter,
            True,
        )

    for value in ("NaN", "Infinity", "-Infinity"):
        with pytest.raises(
            ProcedureParameterValidationError,
            match="Threshold must be a finite number",
        ):
            normalise_procedure_parameter_value(
                parameter,
                value,
            )


def test_decimal_negative_zero_is_canonicalised() -> None:
    """Equivalent zero values should persist with one stable representation."""

    parameter = ProcedureParameterDefinition.create(
        key="threshold",
        label="Threshold",
        value_type=ProcedureParameterType.DECIMAL,
    )

    assert (
        normalise_procedure_parameter_value(
            parameter,
            "-0.000",
        )
        == "0"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (5, 5),
        (5.0, 5),
        ("1,250", 1250),
    ),
)
def test_integer_parameter_accepts_whole_number_forms(
    value,
    expected,
) -> None:
    """Equivalent whole-number inputs should resolve to an integer."""

    parameter = ProcedureParameterDefinition.create(
        key="minimum_count",
        label="Minimum count",
        value_type=ProcedureParameterType.INTEGER,
    )

    assert (
        normalise_procedure_parameter_value(
            parameter,
            value,
        )
        == expected
    )


@pytest.mark.parametrize(
    "value",
    (
        True,
        2.5,
        float("inf"),
        "12.5",
        "not-a-number",
    ),
)
def test_integer_parameter_rejects_non_whole_numbers(
    value,
) -> None:
    """Invalid integer inputs must fail before procedure execution."""

    parameter = ProcedureParameterDefinition.create(
        key="minimum_count",
        label="Minimum count",
        value_type=ProcedureParameterType.INTEGER,
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Minimum count must be a whole number",
    ):
        normalise_procedure_parameter_value(
            parameter,
            value,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("YES", True),
        ("on", True),
        ("No", False),
        ("off", False),
    ),
)
def test_boolean_parameter_accepts_supported_forms(
    value,
    expected,
) -> None:
    """Supported Boolean forms should resolve deterministically."""

    parameter = ProcedureParameterDefinition.create(
        key="include_reversals",
        label="Include reversals",
        value_type=ProcedureParameterType.BOOLEAN,
    )

    assert (
        normalise_procedure_parameter_value(
            parameter,
            value,
        )
        is expected
    )


def test_boolean_parameter_rejects_ambiguous_value() -> None:
    """Unsupported Boolean text should not be guessed."""

    parameter = ProcedureParameterDefinition.create(
        key="include_reversals",
        label="Include reversals",
        value_type=ProcedureParameterType.BOOLEAN,
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Include reversals must be Yes or No",
    ):
        normalise_procedure_parameter_value(
            parameter,
            "maybe",
        )


def test_choice_parameter_uses_canonical_configured_label() -> None:
    """Single-choice values should be matched case-insensitively."""

    parameter = ProcedureParameterDefinition.create(
        key="comparison_mode",
        label="Comparison mode",
        value_type=ProcedureParameterType.CHOICE,
        choices=("Exact", "Normalised"),
    )

    assert (
        normalise_procedure_parameter_value(
            parameter,
            "normalised",
        )
        == "Normalised"
    )


def test_choice_parameter_rejects_unknown_selection() -> None:
    """An unknown choice must not silently alter procedure behaviour."""

    parameter = ProcedureParameterDefinition.create(
        key="comparison_mode",
        label="Comparison mode",
        value_type=ProcedureParameterType.CHOICE,
        choices=("Exact", "Normalised"),
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Comparison mode must be one of",
    ):
        normalise_procedure_parameter_value(
            parameter,
            "Fuzzy",
        )


def test_multi_choice_string_is_split_deduplicated_and_canonicalised() -> None:
    """Delimited multi-choice input should become stable unique labels."""

    parameter = ProcedureParameterDefinition.create(
        key="weekend_days",
        label="Weekend days",
        value_type=ProcedureParameterType.MULTI_CHOICE,
        choices=("Friday", "Saturday", "Sunday"),
    )

    assert normalise_procedure_parameter_value(
        parameter,
        "saturday; Sunday\nSATURDAY",
    ) == [
        "Saturday",
        "Sunday",
    ]


def test_multi_choice_rejects_unknown_value() -> None:
    """Unsupported selections should fail instead of being ignored."""

    parameter = ProcedureParameterDefinition.create(
        key="weekend_days",
        label="Weekend days",
        value_type=ProcedureParameterType.MULTI_CHOICE,
        choices=("Saturday", "Sunday"),
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="contains an unsupported value",
    ):
        normalise_procedure_parameter_value(
            parameter,
            ["Saturday", "Monday"],
        )


@pytest.mark.parametrize(
    "value",
    (
        {"Manual": True},
        123,
    ),
)
def test_text_list_rejects_mapping_and_scalar_inputs(
    value,
) -> None:
    """List parameters require delimited text or an iterable of values."""

    parameter = ProcedureParameterDefinition.create(
        key="journal_values",
        label="Journal values",
        value_type=ProcedureParameterType.TEXT_LIST,
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="must contain one or more text values",
    ):
        normalise_procedure_parameter_value(
            parameter,
            value,
        )


def test_required_list_cannot_normalise_to_empty() -> None:
    """Required list values must remain populated after cleanup."""

    definition = ProcedureDefinition.create(
        procedure_id="TEST001",
        name="Parameter validation test",
        category="Test",
        parameter_definitions=(
            ProcedureParameterDefinition.create(
                key="journal_values",
                label="Journal values",
                value_type=ProcedureParameterType.TEXT_LIST,
                required=True,
            ),
        ),
    )

    with pytest.raises(
        ProcedureParameterValidationError,
        match="Journal values is required",
    ):
        resolve_procedure_parameters(
            definition,
            {
                "journal_values": [
                    " ",
                    "",
                ],
            },
        )


def test_parameter_formatter_produces_auditor_facing_values() -> None:
    """Stored parameter values should have concise display representations."""

    boolean_parameter = ProcedureParameterDefinition.create(
        key="include_reversals",
        label="Include reversals",
        value_type=ProcedureParameterType.BOOLEAN,
    )
    list_parameter = ProcedureParameterDefinition.create(
        key="weekend_days",
        label="Weekend days",
        value_type=ProcedureParameterType.MULTI_CHOICE,
        choices=("Saturday", "Sunday"),
    )
    integer_parameter = ProcedureParameterDefinition.create(
        key="minimum_count",
        label="Minimum count",
        value_type=ProcedureParameterType.INTEGER,
    )

    assert (
        format_procedure_parameter_value(
            boolean_parameter,
            True,
        )
        == "Yes"
    )
    assert (
        format_procedure_parameter_value(
            boolean_parameter,
            False,
        )
        == "No"
    )
    assert (
        format_procedure_parameter_value(
            list_parameter,
            ["Saturday", "Sunday"],
        )
        == "Saturday, Sunday"
    )
    assert (
        format_procedure_parameter_value(
            integer_parameter,
            25,
        )
        == "25"
    )
