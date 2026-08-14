"""Tests for canonical audit-procedure identity and GL catalogue."""

import pytest

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
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
    with pytest.raises(ValueError, match="Legacy FA-GL"):
        canonical_procedure_id("FA-GL-001")


def test_execution_request_persists_canonical_identifier() -> None:
    request = AuditExecutionRequest.create(
        procedure_id="GL-003",
        dataset_id="dataset-123",
    )

    assert request.procedure_id == "GL003"
    assert request.execution_key == "GL003:dataset-123"


def test_execution_request_rejects_legacy_methodology_reference() -> None:
    with pytest.raises(ValueError, match="Legacy FA-GL"):
        AuditExecutionRequest.create(
            procedure_id="FA-GL-001",
            dataset_id="dataset-123",
        )


def test_catalogue_contains_33_unique_engine_procedures() -> None:
    procedure_ids = [definition.procedure_id for definition in GENERAL_LEDGER_PROCEDURES]

    assert len(procedure_ids) == 33
    assert len(set(procedure_ids)) == 33


def test_readiness_ranks_are_complete_and_unique() -> None:
    ranks = [definition.readiness_rank for definition in GENERAL_LEDGER_PROCEDURES]

    assert ranks == list(range(1, 34))


def test_weekend_transactions_has_canonical_gl003_identity() -> None:
    definition = require_general_ledger_procedure("GL003")

    assert definition.name == "Weekend Transactions"
    assert definition.display_id == "GL-003"
    assert definition.readiness_rank == 1
    assert definition.readiness_score == 90


def test_lookup_accepts_display_form_without_changing_identity() -> None:
    canonical = require_general_ledger_procedure("GL003")
    display = require_general_ledger_procedure("GL-003")

    assert display is canonical


def test_unknown_procedure_returns_none_from_optional_lookup() -> None:
    assert get_general_ledger_procedure("GL999") is None


def test_unknown_procedure_raises_from_required_lookup() -> None:
    with pytest.raises(KeyError, match="GL999"):
        require_general_ledger_procedure("GL999")
