"""Tests for the generic audit-procedure definition contract."""

import pytest

from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)


def test_definition_normalises_procedure_identity() -> None:
    """Definitions should store canonical procedure identifiers."""

    definition = ProcedureDefinition.create(
        procedure_id="gl-003",
        name="Weekend Transactions",
        category="General Ledger",
    )

    assert definition.procedure_id == "GL003"
    assert definition.display_id == "GL-003"


def test_definition_supports_non_gl_procedure_families() -> None:
    """The definition contract must not be tied to General Ledger."""

    definition = ProcedureDefinition.create(
        procedure_id="PAY-001",
        name="Example Payroll Procedure",
        category="Payroll",
    )

    assert definition.procedure_id == "PAY001"
    assert definition.display_id == "PAY-001"


def test_definition_cleans_descriptive_values() -> None:
    """User-facing definition text should be normalised."""

    definition = ProcedureDefinition.create(
        procedure_id="GL003",
        name="  Weekend Transactions  ",
        category="  General Ledger  ",
        description="  Review weekend activity.  ",
        procedure_version=" 1.2 ",
    )

    assert definition.name == "Weekend Transactions"
    assert definition.category == "General Ledger"
    assert definition.description == "Review weekend activity."
    assert definition.procedure_version == "1.2"


def test_definition_keeps_required_and_helpful_fields() -> None:
    """Procedure field requirements should be stored explicitly."""

    definition = ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        required_fields=("transaction_date",),
        helpful_fields=(
            "journal_number",
            "description",
        ),
    )

    assert definition.required_fields == ("transaction_date",)

    assert definition.helpful_fields == (
        "journal_number",
        "description",
    )

    assert definition.all_fields == (
        "transaction_date",
        "journal_number",
        "description",
    )


@pytest.mark.parametrize(
    ("name", "category", "version", "message"),
    (
        (
            "",
            "General Ledger",
            "1.0",
            "Procedure name",
        ),
        (
            "Example",
            "",
            "1.0",
            "Procedure category",
        ),
        (
            "Example",
            "General Ledger",
            "",
            "Procedure version",
        ),
    ),
)
def test_definition_requires_core_metadata(
    name: str,
    category: str,
    version: str,
    message: str,
) -> None:
    """Essential definition metadata cannot be blank."""

    with pytest.raises(
        ValueError,
        match=message,
    ):
        ProcedureDefinition.create(
            procedure_id="GL003",
            name=name,
            category=category,
            procedure_version=version,
        )


def test_definition_rejects_blank_standard_field() -> None:
    """Field requirements cannot contain blank keys."""

    with pytest.raises(
        ValueError,
        match="Required field cannot be blank",
    ):
        ProcedureDefinition.create(
            procedure_id="GL003",
            name="Weekend Transactions",
            category="General Ledger",
            required_fields=(
                "transaction_date",
                "",
            ),
        )


def test_definition_rejects_duplicate_standard_field() -> None:
    """A field should appear only once in each requirement group."""

    with pytest.raises(
        ValueError,
        match="Required field is duplicated",
    ):
        ProcedureDefinition.create(
            procedure_id="GL003",
            name="Weekend Transactions",
            category="General Ledger",
            required_fields=(
                "transaction_date",
                "transaction_date",
            ),
        )


def test_definition_rejects_required_helpful_overlap() -> None:
    """A field cannot simultaneously be required and merely helpful."""

    with pytest.raises(
        ValueError,
        match="both required and helpful",
    ):
        ProcedureDefinition.create(
            procedure_id="GL003",
            name="Weekend Transactions",
            category="General Ledger",
            required_fields=("transaction_date",),
            helpful_fields=("transaction_date",),
        )


def test_definition_rejects_legacy_methodology_identifier() -> None:
    """Legacy methodology references remain explicitly unsupported."""

    with pytest.raises(
        ValueError,
        match="Legacy FA-GL",
    ):
        ProcedureDefinition.create(
            procedure_id="FA-GL-003",
            name="Weekend Transactions",
            category="General Ledger",
        )
