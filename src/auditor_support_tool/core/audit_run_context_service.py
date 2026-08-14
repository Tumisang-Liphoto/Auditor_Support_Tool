"""Build reproducible audit-procedure run contexts."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureRunContext,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    PreparedAuditDataset,
)
from auditor_support_tool.core.source_integrity_service import (
    SourceIntegrityService,
)


class AuditRunContextError(RuntimeError):
    """Raised when an audit run context cannot be created safely."""


class AuditRunContextService:
    """Build run context from the actual source and prepared dataset."""

    def __init__(
        self,
        source_integrity_service: SourceIntegrityService | None = None,
    ) -> None:
        self._source_integrity_service = source_integrity_service or SourceIntegrityService()

    def build(
        self,
        *,
        request: AuditExecutionRequest,
        prepared_dataset: PreparedAuditDataset,
        source_path: str | Path,
        procedure_version: str,
        parameters: Mapping[str, object] | None = None,
    ) -> ProcedureRunContext:
        """Return the reproducibility context for one audit-procedure run."""

        if request.dataset_id != prepared_dataset.dataset_id:
            raise AuditRunContextError(
                "Execution request dataset does not match the prepared audit dataset."
            )

        try:
            source_sha256 = self._source_integrity_service.sha256_file(source_path)
        except (FileNotFoundError, OSError) as error:
            raise AuditRunContextError(
                f"Could not calculate source-file integrity hash: {error}"
            ) from error

        return ProcedureRunContext.create(
            request=request,
            procedure_version=procedure_version,
            source_sha256=source_sha256,
            mapping_fingerprint=prepared_dataset.mapping_fingerprint,
            parameters=parameters,
        )
