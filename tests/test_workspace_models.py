"""Tests for persistent workspace models."""

from pathlib import Path

import pytest

from auditor_support_tool.core.workspace_models import (
    WORKSPACE_FORMAT_VERSION,
    WorkspaceDocument,
    WorkspaceIdentity,
    WorkspaceSourceReference,
)


def test_workspace_identity_requires_name() -> None:
    """A workspace cannot be created without a name."""

    with pytest.raises(ValueError, match="Workspace name is required"):
        WorkspaceIdentity.create(name="   ")


def test_workspace_identity_creates_unique_identifier() -> None:
    """Each new workspace receives its own identifier."""

    first = WorkspaceIdentity.create(name="First")
    second = WorkspaceIdentity.create(name="Second")

    assert first.workspace_id
    assert second.workspace_id
    assert first.workspace_id != second.workspace_id


def test_workspace_identity_cleans_text_values() -> None:
    """Workspace identity text values are stripped."""

    identity = WorkspaceIdentity.create(
        name="  Payroll Audit  ",
        auditee_name="  Example Organisation  ",
        audit_year="  2026  ",
        audit_domain="  Financial Audit  ",
        audit_area="  Payroll  ",
        lead_auditor="  Auditor One  ",
        description="  Payroll data review  ",
    )

    assert identity.name == "Payroll Audit"
    assert identity.auditee_name == "Example Organisation"
    assert identity.audit_year == "2026"
    assert identity.audit_domain == "Financial Audit"
    assert identity.audit_area == "Payroll"
    assert identity.lead_auditor == "Auditor One"
    assert identity.description == "Payroll data review"


def test_workspace_document_uses_current_format_version() -> None:
    """A new workspace document uses the supported format version."""

    identity = WorkspaceIdentity.create(name="Payroll Audit")

    document = WorkspaceDocument.create(
        identity=identity,
        application_version="0.1.2-beta.2",
    )

    assert document.format_version == WORKSPACE_FORMAT_VERSION
    assert document.application_version == "0.1.2-beta.2"
    assert document.identity is identity
    assert document.active_dataset_id is None
    assert document.source is None
    assert document.workbook_package is None
    assert document.field_mappings == {}
    assert document.transformation_history == []
    assert document.data_quality_issues == []


def test_source_reference_records_existing_file(tmp_path: Path) -> None:
    """A source reference records a valid source file."""

    source_path = tmp_path / "general-ledger.csv"
    source_path.write_text(
        "id,amount\n1,100\n",
        encoding="utf-8",
    )

    reference = WorkspaceSourceReference.from_path(source_path)

    assert reference.file_name == "general-ledger.csv"
    assert reference.path == source_path.resolve()
    assert reference.exists is True
    assert reference.file_size_bytes == source_path.stat().st_size
    assert reference.modified_at is not None


def test_source_reference_rejects_missing_file(tmp_path: Path) -> None:
    """A missing source file cannot be registered."""

    with pytest.raises(FileNotFoundError, match="Source file not found"):
        WorkspaceSourceReference.from_path(
            tmp_path / "missing.xlsx",
        )
