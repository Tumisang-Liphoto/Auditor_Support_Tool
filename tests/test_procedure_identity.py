"""Tests for generic audit-procedure identifiers."""

import pytest

from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
    procedure_display_id,
)


@pytest.mark.parametrize(
    ("supplied", "expected"),
    (
        ("GL003", "GL003"),
        ("GL-003", "GL003"),
        ("gl003", "GL003"),
        (" gl-003 ", "GL003"),
        ("PAY001", "PAY001"),
        ("PAY-001", "PAY001"),
        ("PROC012", "PROC012"),
        ("PROC-012", "PROC012"),
        ("ITGC004", "ITGC004"),
        ("ITGC-004", "ITGC004"),
    ),
)
def test_canonical_procedure_id_accepts_generic_identifiers(
    supplied: str,
    expected: str,
) -> None:
    """Procedure identifiers should not be tied to one audit domain."""

    assert canonical_procedure_id(supplied) == expected


@pytest.mark.parametrize(
    ("supplied", "expected"),
    (
        ("GL003", "GL-003"),
        ("PAY001", "PAY-001"),
        ("PROC012", "PROC-012"),
        ("ITGC004", "ITGC-004"),
    ),
)
def test_procedure_display_id_formats_generic_identifiers(
    supplied: str,
    expected: str,
) -> None:
    """Display identifiers should preserve the full procedure prefix."""

    assert procedure_display_id(supplied) == expected


@pytest.mark.parametrize(
    "supplied",
    (
        "",
        "G001",
        "GL01",
        "GL0001",
        "GL-01",
        "GL_003",
        "GL 003",
        "123003",
    ),
)
def test_invalid_procedure_identifiers_are_rejected(
    supplied: str,
) -> None:
    """Malformed or legacy identifiers should be rejected."""

    with pytest.raises(
        ValueError,
        match="Procedure identifier",
    ):
        canonical_procedure_id(supplied)


def test_legacy_methodology_identifier_is_rejected_explicitly() -> None:
    """Legacy methodology references should not be converted automatically."""

    with pytest.raises(
        ValueError,
        match="Legacy FA-GL",
    ):
        canonical_procedure_id("FA-GL-003")
