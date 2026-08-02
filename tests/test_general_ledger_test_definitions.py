"""Tests for registered General Ledger audit fields and tests."""

from auditor_support_tool.domains.financial_audit.general_ledger.test_definitions import (
    GENERAL_LEDGER_FIELDS,
    GENERAL_LEDGER_TESTS,
    GL_001_DUPLICATE_INVOICES,
    GL_003_WEEKEND_POSTINGS,
    get_field_definition,
    get_test_definition,
)


def test_standard_field_keys_are_unique() -> None:
    """Each standard audit field should have one unique key."""

    field_keys = [field_definition.key for field_definition in GENERAL_LEDGER_FIELDS]

    assert len(field_keys) == len(set(field_keys))


def test_registered_test_codes_are_unique() -> None:
    """Each registered audit test should have one unique code."""

    test_codes = [test_definition.code for test_definition in GENERAL_LEDGER_TESTS]

    assert len(test_codes) == len(set(test_codes))


def test_gl_001_requires_invoice_number() -> None:
    """Duplicate invoice detection should require an invoice number."""

    assert GL_001_DUPLICATE_INVOICES.required_fields == ("invoice_number",)

    assert "vendor_number" in GL_001_DUPLICATE_INVOICES.helpful_fields
    assert "transaction_date" in GL_001_DUPLICATE_INVOICES.helpful_fields


def test_gl_003_requires_transaction_date() -> None:
    """Weekend posting detection should require a transaction date."""

    assert GL_003_WEEKEND_POSTINGS.required_fields == ("transaction_date",)

    assert "journal_number" in GL_003_WEEKEND_POSTINGS.helpful_fields
    assert "net_amount" in GL_003_WEEKEND_POSTINGS.helpful_fields


def test_all_test_fields_are_registered_standard_fields() -> None:
    """Test requirements should reference known standard field keys."""

    registered_field_keys = {field_definition.key for field_definition in GENERAL_LEDGER_FIELDS}

    for test_definition in GENERAL_LEDGER_TESTS:
        assert set(test_definition.required_fields) <= registered_field_keys
        assert set(test_definition.helpful_fields) <= registered_field_keys


def test_get_field_definition_returns_requested_field() -> None:
    """A standard field should be retrievable by its key."""

    field_definition = get_field_definition("invoice_number")

    assert field_definition is not None
    assert field_definition.label == "Invoice Number"


def test_get_test_definition_is_case_insensitive() -> None:
    """Registered tests should be retrievable without case sensitivity."""

    test_definition = get_test_definition("gl-003")

    assert test_definition is GL_003_WEEKEND_POSTINGS


def test_unknown_field_and_test_return_none() -> None:
    """Unknown identifiers should not resolve to unrelated definitions."""

    assert get_field_definition("unknown_field") is None
    assert get_test_definition("GL-999") is None
