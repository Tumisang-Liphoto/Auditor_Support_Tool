"""Tests for generic audit-procedure parameter metadata and persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from auditor_support_tool.core.constants import APP_VERSION
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_parameter_models import (
    ProcedureParameterDefinition,
    ProcedureParameterType,
)
from auditor_support_tool.core.workspace_models import (
    WorkspaceDocument,
    WorkspaceIdentity,
)
from auditor_support_tool.core.workspace_service import WorkspaceService
from auditor_support_tool.core.workspace_state import WorkspaceState


def _workspace_service(tmp_path: Path) -> WorkspaceService:
    """Return a service with isolated paths needed by workspace persistence."""

    paths = SimpleNamespace(
        workspaces=tmp_path / "workspaces",
        workspace_backups=tmp_path / "backups",
    )

    return WorkspaceService(paths)  # type: ignore[arg-type]


def test_parameter_definition_normalises_metadata() -> None:
    """Generic parameter metadata should have a stable validated contract."""

    definition = ProcedureParameterDefinition.create(
        key=" high_value_threshold ",
        label=" High-value threshold ",
        value_type=ProcedureParameterType.DECIMAL,
        description=" Optional engagement threshold. ",
    )

    assert definition.key == "high_value_threshold"
    assert definition.label == "High-value threshold"
    assert definition.value_type == ProcedureParameterType.DECIMAL
    assert definition.description == "Optional engagement threshold."
    assert definition.required is False


def test_procedure_definition_exposes_parameter_keys() -> None:
    """Procedure definitions should expose parameter metadata without execution logic."""

    threshold = ProcedureParameterDefinition.create(
        key="high_value_threshold",
        label="High-value threshold",
        value_type=ProcedureParameterType.DECIMAL,
    )
    manual_values = ProcedureParameterDefinition.create(
        key="manual_journal_values",
        label="Manual-journal values",
        value_type=ProcedureParameterType.TEXT_LIST,
    )

    definition = ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        parameter_definitions=(
            threshold,
            manual_values,
        ),
    )

    assert definition.parameter_keys == (
        "high_value_threshold",
        "manual_journal_values",
    )

    with pytest.raises(ValueError, match="duplicated"):
        ProcedureDefinition.create(
            procedure_id="GL003",
            name="Weekend Transactions",
            category="General Ledger",
            parameter_definitions=(
                threshold,
                threshold,
            ),
        )


def test_workspace_state_stores_canonical_procedure_parameters() -> None:
    """Workspace state should retain defensive JSON-safe parameter values."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="General Ledger Audit"))
    state.mark_saved()

    values = {
        "high_value_threshold": "100000",
        "manual_journal_values": (
            "Manual",
            "Adjustment",
        ),
    }

    state.set_procedure_parameters(
        "GL-003",
        values,
    )

    assert state.is_dirty is True
    assert state.get_procedure_parameters("GL003") == {
        "high_value_threshold": "100000",
        "manual_journal_values": [
            "Manual",
            "Adjustment",
        ],
    }

    returned = state.get_procedure_parameters("GL003")
    returned["high_value_threshold"] = "1"

    assert state.get_procedure_parameters("GL003")["high_value_threshold"] == "100000"


def test_workspace_state_rejects_non_serialisable_parameter_values() -> None:
    """Workspace persistence should reject values JSON cannot reproduce safely."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="General Ledger Audit"))

    with pytest.raises(
        TypeError,
        match="JSON-compatible",
    ):
        state.set_procedure_parameters(
            "GL003",
            {"high_value_threshold": Decimal("100000")},
        )


def test_procedure_parameters_round_trip_through_workspace_service(
    tmp_path: Path,
) -> None:
    """Saved procedure parameters should survive closing and reopening a workspace."""

    service = _workspace_service(tmp_path)

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="General Ledger Audit"))
    state.set_procedure_parameters(
        "GL003",
        {
            "high_value_threshold": "75000",
            "manual_journal_values": [
                "Manual",
                "Adjustment",
            ],
        },
    )

    workspace_path = service.save_state(
        state,
        tmp_path / "gl-audit.astworkspace",
    )

    reopened_state = WorkspaceState()
    loaded = service.load_into_state(
        reopened_state,
        workspace_path,
    )

    expected = {
        "GL003": {
            "high_value_threshold": "75000",
            "manual_journal_values": [
                "Manual",
                "Adjustment",
            ],
        }
    }

    assert loaded.procedure_parameters == expected
    assert reopened_state.procedure_parameters == expected
    assert reopened_state.is_dirty is False


def test_older_workspace_without_parameter_store_remains_compatible(
    tmp_path: Path,
) -> None:
    """The optional parameter store must not break existing version-1 workspaces."""

    service = _workspace_service(tmp_path)
    document = WorkspaceDocument.create(
        identity=WorkspaceIdentity.create(name="Existing Workspace"),
        application_version=APP_VERSION,
    )

    payload = asdict(document)
    payload.pop("procedure_parameters")

    workspace_path = tmp_path / "existing.astworkspace"
    workspace_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    loaded = service.load_document(workspace_path)

    assert loaded.procedure_parameters == {}
