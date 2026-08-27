"""Catalogue and resource lookup for bundled audit test descriptions."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)


@dataclass(frozen=True, slots=True)
class TestDescriptionDefinition:
    """Description of one bundled audit-test document."""

    test_code: str
    title: str
    category: str
    description: str
    file_name: str


TEST_DESCRIPTIONS: tuple[TestDescriptionDefinition, ...] = (
    TestDescriptionDefinition(
        test_code="GL-001",
        title="Duplicate Invoice Detection",
        category="General Ledger",
        description=(
            "Identifies repeated invoice numbers that may require further audit scrutiny."
        ),
        file_name="GL-001-Duplicate-Invoice-Detection.pdf",
    ),
    TestDescriptionDefinition(
        test_code="GL-003",
        title="Weekend Postings",
        category="General Ledger",
        description=(
            "Identifies general ledger transactions dated on Saturdays "
            "or Sundays for further audit scrutiny."
        ),
        file_name="GL-003-Weekend-Postings.pdf",
    ),
    TestDescriptionDefinition(
        test_code="GL-006",
        title="Segregation of Duties",
        category="General Ledger",
        description=(
            "Identifies transactions entered and approved by the same "
            "user for further audit scrutiny."
        ),
        file_name="GL-006-Segregation-of-Duties.pdf",
    ),
)


def get_test_description_definition(
    test_code: str,
) -> TestDescriptionDefinition | None:
    """Return a bundled description by canonical or display procedure ID."""

    try:
        requested = canonical_procedure_id(test_code)
    except ValueError:
        return None

    for definition in TEST_DESCRIPTIONS:
        if canonical_procedure_id(definition.test_code) == requested:
            return definition

    return None


def test_descriptions_directory() -> Path:
    """Return the bundled General Ledger description directory."""

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return (
            Path(sys._MEIPASS)
            / "auditor_support_tool"
            / "resources"
            / "test_descriptions"
            / "general_ledger"
        )

    return (
        Path(__file__).resolve().parents[1] / "resources" / "test_descriptions" / "general_ledger"
    )


def description_document_path(
    definition: TestDescriptionDefinition,
) -> Path:
    """Return the expected bundled path for one description."""

    return test_descriptions_directory() / definition.file_name


def has_test_description_document(
    test_code: str,
) -> bool:
    """Return whether a bundled description PDF exists for the procedure."""

    definition = get_test_description_definition(test_code)

    if definition is None:
        return False

    return description_document_path(definition).is_file()
