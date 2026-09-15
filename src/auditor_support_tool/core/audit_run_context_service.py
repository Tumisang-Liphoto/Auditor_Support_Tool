"""Build reproducible audit-procedure run contexts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExecutorIdentity,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.source_integrity_service import (
    SourceIntegrityService,
)


class AuditRunContextError(RuntimeError):
    """Raised when an audit run context cannot be created safely."""


class AuditRunContextService:
    """Build run context from source, mappings and audit scope."""

    def __init__(
        self,
        source_integrity_service: SourceIntegrityService | None = None,
        executor_identity: ProcedureExecutorIdentity | None = None,
        executor_identity_provider: Callable[[], ProcedureExecutorIdentity] | None = None,
    ) -> None:
        self._source_integrity_service = source_integrity_service or SourceIntegrityService()

        if executor_identity is not None and not isinstance(
            executor_identity, ProcedureExecutorIdentity
        ):
            raise TypeError("Executor identity must be a ProcedureExecutorIdentity.")

        if executor_identity is not None and executor_identity_provider is not None:
            raise ValueError(
                "Provide either a fixed executor identity or an executor identity "
                "provider, not both."
            )

        self._executor_identity = executor_identity or ProcedureExecutorIdentity()
        self._executor_identity_provider = executor_identity_provider

    def build(
        self,
        *,
        request: AuditExecutionRequest,
        record_source: AuditRecordSource,
        source_path: str | Path,
        procedure_version: str,
        audit_period_start: str = "",
        audit_period_end: str = "",
        parameters: Mapping[str, object] | None = None,
    ) -> ProcedureRunContext:
        """Return the reproducibility context for one procedure run."""

        if request.dataset_id != record_source.dataset_id:
            raise AuditRunContextError(
                "Execution request dataset does not match the audit record source."
            )

        try:
            loaded_sha256 = getattr(record_source, "source_sha256", "")
            if not loaded_sha256:
                raise AuditRunContextError(
                    "The loaded source fingerprint is unavailable. Reload the source data "
                    "before running audit procedures."
                )
            source_sha256 = self._source_integrity_service.sha256_file(source_path)
        except (
            FileNotFoundError,
            OSError,
        ) as error:
            raise AuditRunContextError(
                "Could not verify the loaded source file. Restore or reload the source data "
                "before running audit procedures."
            ) from error

        if source_sha256 != loaded_sha256:
            raise AuditRunContextError(
                "The source file has changed since it was loaded. Reload the source data "
                "before running audit procedures."
            )

        executor_identity = self._executor_identity

        if self._executor_identity_provider is not None:
            executor_identity = self._executor_identity_provider()

            if not isinstance(executor_identity, ProcedureExecutorIdentity):
                raise TypeError(
                    "Executor identity provider must return a ProcedureExecutorIdentity."
                )

        return ProcedureRunContext.create(
            request=request,
            procedure_version=procedure_version,
            source_sha256=loaded_sha256,
            mapping_fingerprint=(record_source.mapping_fingerprint),
            audit_period_start=audit_period_start,
            audit_period_end=audit_period_end,
            executor=executor_identity,
            parameters=parameters,
        )
