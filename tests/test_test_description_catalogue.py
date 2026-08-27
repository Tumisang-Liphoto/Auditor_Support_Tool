"""Tests for bundled test-description catalogue lookup."""

from pathlib import Path

from auditor_support_tool.core.test_description_catalogue import (
    TEST_DESCRIPTIONS,
    description_document_path,
    get_test_description_definition,
    has_test_description_document,
)


def test_description_lookup_accepts_canonical_identifier() -> None:
    """Canonical procedure IDs should resolve bundled descriptions."""

    definition = get_test_description_definition("GL003")

    assert definition is not None
    assert definition.test_code == "GL-003"
    assert definition.title == "Weekend Postings"


def test_description_lookup_accepts_display_identifier() -> None:
    """Display-form procedure IDs should resolve the same description."""

    canonical = get_test_description_definition("GL001")
    display = get_test_description_definition("GL-001")

    assert canonical is not None
    assert display is canonical


def test_gl006_description_is_bundled() -> None:
    """The implemented GL-006 procedure should expose its description PDF."""

    definition = get_test_description_definition("GL006")

    assert definition is not None
    assert definition.test_code == "GL-006"
    assert definition.title == "Segregation of Duties"
    assert has_test_description_document("GL006") is True


def test_unknown_test_description_returns_none() -> None:
    """Procedures without a bundled description should not be invented."""

    assert get_test_description_definition("GL999") is None


def test_description_paths_use_catalogue_file_names() -> None:
    """Resource paths should be derived from the catalogue definition."""

    paths = tuple(description_document_path(definition) for definition in TEST_DESCRIPTIONS)

    assert all(isinstance(path, Path) for path in paths)
    assert tuple(path.name for path in paths) == (
        "GL-001-Duplicate-Invoice-Detection.pdf",
        "GL-003-Weekend-Postings.pdf",
        "GL-006-Segregation-of-Duties.pdf",
    )
