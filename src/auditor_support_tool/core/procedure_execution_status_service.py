"""Evaluate whether a successful procedure run still matches current inputs."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
    normalise_execution_parameters,
)
from auditor_support_tool.core.source_integrity_service import (
    SourceIntegrityService,
)


class ProcedureExecutionStatus(StrEnum):
    """User-facing execution state for an available procedure."""

    NOT_RUN = "not_run"
    COMPLETED = "completed"
    NEEDS_RERUN = "needs_rerun"


class ProcedureDefinitionLike(Protocol):
    """Definition attributes required for execution-status checks."""

    procedure_version: str


class AuditRecordSourceLike(Protocol):
    """Record-source attributes required for execution-status checks."""

    dataset_id: str
    mapping_fingerprint: str


class ProcedureExecutionStatusService:
    """Compare the last successful run with current execution inputs."""

    def __init__(
        self,
        *,
        source_integrity_service: SourceIntegrityService | None = None,
    ) -> None:
        self._source_integrity_service = source_integrity_service or SourceIntegrityService()
        self._source_hash_cache: dict[
            tuple[str, int, int],
            str,
        ] = {}

    def evaluate(
        self,
        *,
        definition: ProcedureDefinitionLike,
        source: AuditRecordSourceLike,
        source_path: str | Path,
        parameters: Mapping[str, object],
        audit_period_start: str,
        audit_period_end: str,
        stamp: ProcedureExecutionStamp | None,
    ) -> ProcedureExecutionStatus:
        """Return Not Run, Completed or Needs Re-run."""

        if stamp is None:
            return ProcedureExecutionStatus.NOT_RUN

        if stamp.dataset_id != source.dataset_id:
            return ProcedureExecutionStatus.NOT_RUN

        if stamp.procedure_version != definition.procedure_version.strip():
            return ProcedureExecutionStatus.NEEDS_RERUN

        if stamp.mapping_fingerprint != source.mapping_fingerprint:
            return ProcedureExecutionStatus.NEEDS_RERUN

        if (stamp.parameters or {}) != normalise_execution_parameters(parameters):
            return ProcedureExecutionStatus.NEEDS_RERUN

        if stamp.audit_period_start != audit_period_start.strip():
            return ProcedureExecutionStatus.NEEDS_RERUN

        if stamp.audit_period_end != audit_period_end.strip():
            return ProcedureExecutionStatus.NEEDS_RERUN

        try:
            current_source_hash = self._source_sha256(source_path)
        except (
            FileNotFoundError,
            OSError,
        ):
            return ProcedureExecutionStatus.NEEDS_RERUN

        if stamp.source_sha256 != current_source_hash:
            return ProcedureExecutionStatus.NEEDS_RERUN

        return ProcedureExecutionStatus.COMPLETED

    def remember_source_hash(
        self,
        source_path: str | Path,
        source_sha256: str,
    ) -> None:
        """Cache a hash already calculated by the Test Engine."""

        path = Path(source_path).expanduser().resolve()
        status = path.stat()

        cache_key = (
            str(path),
            status.st_size,
            status.st_mtime_ns,
        )

        self._source_hash_cache = {
            key: value for key, value in self._source_hash_cache.items() if key[0] != str(path)
        }
        self._source_hash_cache[cache_key] = source_sha256.strip().lower()

    def _source_sha256(
        self,
        source_path: str | Path,
    ) -> str:
        """Return the current source hash, cached by inexpensive file metadata."""

        path = Path(source_path).expanduser().resolve()
        status = path.stat()

        cache_key = (
            str(path),
            status.st_size,
            status.st_mtime_ns,
        )

        cached = self._source_hash_cache.get(cache_key)

        if cached is not None:
            return cached

        source_hash = self._source_integrity_service.sha256_file(path)

        # Retain only the newest cache entry for this path.
        self._source_hash_cache = {
            key: value for key, value in self._source_hash_cache.items() if key[0] != str(path)
        }
        self._source_hash_cache[cache_key] = source_hash

        return source_hash
