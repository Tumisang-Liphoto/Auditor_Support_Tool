"""Tests for procedure execution status evaluation."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
)
from auditor_support_tool.core.procedure_execution_status_service import (
    ProcedureExecutionStatus,
    ProcedureExecutionStatusService,
)


def create_source_file(
    tmp_path: Path,
    content: bytes = b"source-data",
) -> tuple[Path, str]:
    """Create a small source file and return its SHA-256 digest."""

    path = tmp_path / "source.xlsx"
    path.write_bytes(content)

    return (
        path,
        hashlib.sha256(content).hexdigest(),
    )


def create_stamp(
    *,
    source_sha256: str,
    mapping_fingerprint: str = "b" * 64,
    procedure_version: str = "1.0",
    dataset_id: str = "dataset-1",
    parameters: dict[str, object] | None = None,
    audit_period_start: str = "2026-01-01",
    audit_period_end: str = "2026-12-31",
) -> ProcedureExecutionStamp:
    """Create a representative successful execution stamp."""

    return ProcedureExecutionStamp.create(
        execution_id="execution-1",
        procedure_id="GL003",
        procedure_version=procedure_version,
        dataset_id=dataset_id,
        source_sha256=source_sha256,
        mapping_fingerprint=mapping_fingerprint,
        audit_period_start=audit_period_start,
        audit_period_end=audit_period_end,
        parameters=parameters or {},
        completed_at="2026-08-25T15:00:00+00:00",
    )


def evaluate(
    *,
    tmp_path: Path,
    stamp: ProcedureExecutionStamp | None,
    source_content: bytes = b"source-data",
    mapping_fingerprint: str = "b" * 64,
    procedure_version: str = "1.0",
    parameters: dict[str, object] | None = None,
    audit_period_start: str = "2026-01-01",
    audit_period_end: str = "2026-12-31",
) -> ProcedureExecutionStatus:
    """Evaluate one representative procedure status."""

    source_path, _source_hash = create_source_file(
        tmp_path,
        source_content,
    )

    definition = SimpleNamespace(
        procedure_version=procedure_version,
    )
    source = SimpleNamespace(
        dataset_id="dataset-1",
        mapping_fingerprint=mapping_fingerprint,
    )

    return ProcedureExecutionStatusService().evaluate(
        definition=definition,
        source=source,
        source_path=source_path,
        parameters=parameters or {},
        audit_period_start=audit_period_start,
        audit_period_end=audit_period_end,
        stamp=stamp,
    )


def test_status_is_not_run_without_successful_execution(
    tmp_path: Path,
) -> None:
    """An unseen procedure/dataset combination should be Not Run."""

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=None,
        )
        == ProcedureExecutionStatus.NOT_RUN
    )


def test_status_is_completed_when_all_inputs_match(
    tmp_path: Path,
) -> None:
    """An unchanged successful run should remain Completed."""

    _source_path, source_hash = create_source_file(tmp_path)

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=create_stamp(
                source_sha256=source_hash,
            ),
        )
        == ProcedureExecutionStatus.COMPLETED
    )


def test_mapping_change_requires_rerun(
    tmp_path: Path,
) -> None:
    """Changing mappings should stale only the matching procedure run."""

    _source_path, source_hash = create_source_file(tmp_path)

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=create_stamp(
                source_sha256=source_hash,
            ),
            mapping_fingerprint="c" * 64,
        )
        == ProcedureExecutionStatus.NEEDS_RERUN
    )


def test_parameter_change_requires_rerun(
    tmp_path: Path,
) -> None:
    """Changing a procedure's own settings should require a re-run."""

    _source_path, source_hash = create_source_file(tmp_path)

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=create_stamp(
                source_sha256=source_hash,
                parameters={
                    "weekend_days": [
                        "Saturday",
                        "Sunday",
                    ],
                },
            ),
            parameters={
                "weekend_days": [
                    "Saturday",
                ],
            },
        )
        == ProcedureExecutionStatus.NEEDS_RERUN
    )


def test_audit_period_change_requires_rerun(
    tmp_path: Path,
) -> None:
    """Changing audit scope should stale the prior execution."""

    _source_path, source_hash = create_source_file(tmp_path)

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=create_stamp(
                source_sha256=source_hash,
            ),
            audit_period_end="2027-12-31",
        )
        == ProcedureExecutionStatus.NEEDS_RERUN
    )


def test_procedure_version_change_requires_rerun(
    tmp_path: Path,
) -> None:
    """A logic-version update must never reuse an older Completed state."""

    _source_path, source_hash = create_source_file(tmp_path)

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=create_stamp(
                source_sha256=source_hash,
            ),
            procedure_version="1.1",
        )
        == ProcedureExecutionStatus.NEEDS_RERUN
    )


def test_source_change_requires_rerun(
    tmp_path: Path,
) -> None:
    """Changing the source file should stale the successful run."""

    _source_path, original_hash = create_source_file(
        tmp_path,
        b"original",
    )

    assert (
        evaluate(
            tmp_path=tmp_path,
            stamp=create_stamp(
                source_sha256=original_hash,
            ),
            source_content=b"changed",
        )
        == ProcedureExecutionStatus.NEEDS_RERUN
    )
