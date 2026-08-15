"""Tests for audit-period capture in procedure run contexts."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecord,
)
from auditor_support_tool.core.audit_run_context_service import (
    AuditRunContextService,
)


class StubRecordSource:
    """Minimal generic source for run-context tests."""

    @property
    def dataset_id(self) -> str:
        return "dataset-123"

    @property
    def record_count(self) -> int:
        return 10

    @property
    def standard_fields(self) -> tuple[str, ...]:
        return ()

    @property
    def mapping_fingerprint(self) -> str:
        return "b" * 64

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        return False

    def iter_records(self) -> Iterator[AuditRecord]:
        raise AssertionError("Run-context creation must not iterate records.")


def create_context(
    *,
    audit_period_start: str = "",
    audit_period_end: str = "",
) -> ProcedureRunContext:
    """Create a run context directly for validation tests."""

    request = AuditExecutionRequest.create(
        procedure_id="PROC001",
        dataset_id="dataset-123",
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        audit_period_start=audit_period_start,
        audit_period_end=audit_period_end,
    )


def test_context_records_valid_audit_period() -> None:
    """A complete audit period should be preserved."""

    context = create_context(
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
    )

    assert context.audit_period_start == "2026-04-01"
    assert context.audit_period_end == "2027-03-31"
    assert context.has_audit_period


def test_context_allows_missing_audit_period() -> None:
    """Old workspaces may still create contexts without a period."""

    context = create_context()

    assert context.audit_period_start == ""
    assert context.audit_period_end == ""
    assert not context.has_audit_period


def test_context_rejects_partial_audit_period() -> None:
    """One period boundary cannot be supplied without the other."""

    with pytest.raises(
        ValueError,
        match="both be provided",
    ):
        create_context(
            audit_period_start="2026-04-01",
        )


def test_context_rejects_invalid_period_date() -> None:
    """Malformed audit-period dates should fail immediately."""

    with pytest.raises(
        ValueError,
        match="start must be a valid",
    ):
        create_context(
            audit_period_start="2026-99-01",
            audit_period_end="2027-03-31",
        )


def test_context_rejects_reversed_audit_period() -> None:
    """Audit-period end cannot precede the start."""

    with pytest.raises(
        ValueError,
        match="end cannot be before",
    ):
        create_context(
            audit_period_start="2027-03-31",
            audit_period_end="2026-04-01",
        )


def test_context_allows_same_day_period() -> None:
    """A one-day audit period is valid."""

    context = create_context(
        audit_period_start="2026-08-15",
        audit_period_end="2026-08-15",
    )

    assert context.has_audit_period


def test_run_context_service_carries_audit_period(
    tmp_path: Path,
) -> None:
    """The service should copy workspace scope into the run context."""

    source_path = tmp_path / "source.csv"
    source_path.write_text(
        "reference,amount\nA001,100\n",
        encoding="utf-8",
    )

    request = AuditExecutionRequest.create(
        procedure_id="PROC001",
        dataset_id="dataset-123",
    )

    context = AuditRunContextService().build(
        request=request,
        record_source=StubRecordSource(),
        source_path=source_path,
        procedure_version="1.0",
        audit_period_start="2026-04-01",
        audit_period_end="2027-03-31",
    )

    assert context.audit_period_start == "2026-04-01"
    assert context.audit_period_end == "2027-03-31"
    assert context.has_audit_period
