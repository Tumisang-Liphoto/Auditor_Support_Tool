"""Tests for canonical audit-procedure identity and GL catalogue."""

import pytest

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
    procedure_display_id,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    GENERAL_LEDGER_PROCEDURES,
    get_general_ledger_procedure,
    require_general_ledger_procedure,
)


def test_canonical_identifier_is_preserved() -> None:
    assert canonical_procedure_id("GL003") == "GL003"


def test_display_identifier_is_normalised_to_canonical() -> None:
    assert canonical_procedure_id("gl-003") == "GL003"


def test_display_identifier_is_derived_from_canonical() -> None:
    assert procedure_display_id("GL003") == "GL-003"


def test_legacy_methodology_reference_is_not_silently_converted() -> None:
    with pytest.raises(
        ValueError,
        match="Legacy FA-GL",
    ):
        canonical_procedure_id("FA-GL-001")


def test_execution_request_persists_canonical_identifier() -> None:
    request = AuditExecutionRequest.create(
        procedure_id="GL-003",
        dataset_id="dataset-123",
    )

    assert request.procedure_id == "GL003"
    assert request.execution_key == "GL003:dataset-123"


def test_execution_request_rejects_legacy_methodology_reference() -> None:
    with pytest.raises(
        ValueError,
        match="Legacy FA-GL",
    ):
        AuditExecutionRequest.create(
            procedure_id="FA-GL-001",
            dataset_id="dataset-123",
        )


def test_catalogue_contains_33_unique_engine_procedures() -> None:
    procedure_ids = [entry.procedure_id for entry in GENERAL_LEDGER_PROCEDURES]

    assert len(procedure_ids) == 33
    assert len(set(procedure_ids)) == 33


def test_all_catalogue_entries_use_generic_procedure_definitions() -> None:
    """GL catalogue entries should use the core definition contract."""

    for entry in GENERAL_LEDGER_PROCEDURES:
        assert isinstance(
            entry.definition,
            ProcedureDefinition,
        )


def test_all_gl_definitions_have_general_ledger_category() -> None:
    """Domain catalogue entries should declare their domain category."""

    assert {entry.category for entry in GENERAL_LEDGER_PROCEDURES} == {
        "General Ledger",
    }


def test_readiness_ranks_are_complete_and_unique() -> None:
    ranks = [entry.readiness_rank for entry in GENERAL_LEDGER_PROCEDURES]

    assert ranks == list(range(1, 34))


def test_weekend_transactions_has_canonical_gl003_identity() -> None:
    entry = require_general_ledger_procedure("GL003")

    assert entry.name == "Weekend Transactions"
    assert entry.display_id == "GL-003"
    assert entry.readiness_rank == 1
    assert entry.readiness_score == 90


def test_gl003_execution_requirements_are_authoritative() -> None:
    """GL003 should expose its execution requirements through the catalogue."""

    entry = require_general_ledger_procedure("GL003")

    assert entry.required_fields == ("transaction_date",)
    assert "journal_number" in entry.helpful_fields
    assert "net_amount" in entry.helpful_fields
    assert entry.procedure_version == "1.0"


def test_gl001_execution_requirements_are_authoritative() -> None:
    """GL001 should expose its execution requirements through the catalogue."""

    entry = require_general_ledger_procedure("GL001")

    assert entry.required_fields == ("invoice_number",)
    assert "vendor_number" in entry.helpful_fields
    assert "transaction_date" in entry.helpful_fields
    assert entry.procedure_version == "1.0"


def test_unresolved_procedure_requirements_are_not_invented() -> None:
    """Procedures not yet formally defined should retain empty requirements."""

    entry = require_general_ledger_procedure("GL006")

    assert entry.required_fields == ()
    assert entry.helpful_fields == ()


def test_lookup_accepts_display_form_without_changing_identity() -> None:
    canonical = require_general_ledger_procedure("GL003")
    display = require_general_ledger_procedure("GL-003")

    assert display is canonical


def test_unknown_procedure_returns_none_from_optional_lookup() -> None:
    assert get_general_ledger_procedure("GL999") is None


def test_unknown_procedure_raises_from_required_lookup() -> None:
    with pytest.raises(
        KeyError,
        match="GL999",
    ):
        require_general_ledger_procedure("GL999")
