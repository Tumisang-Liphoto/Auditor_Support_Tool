"""Persistent metadata describing successful audit-procedure executions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExecutorIdentity,
    ProcedureRunContext,
)
from auditor_support_tool.core.currency import normalise_currency_code
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)


@dataclass(frozen=True, slots=True)
class ProcedureExecutionStamp:
    """Reproducibility stamp for one successful procedure run."""

    execution_id: str
    procedure_id: str
    procedure_version: str
    dataset_id: str

    source_sha256: str
    mapping_fingerprint: str
    completed_at: str

    audit_period_start: str = ""
    audit_period_end: str = ""
    audit_currency: str = ""

    executor: ProcedureExecutorIdentity = field(default_factory=ProcedureExecutorIdentity)
    parameters: dict[str, object] | None = None

    @classmethod
    def from_context(
        cls,
        context: ProcedureRunContext,
        *,
        completed_at: str,
    ) -> ProcedureExecutionStamp:
        """Create a persistent stamp from a successful run and its completion time."""

        return cls.create(
            execution_id=context.execution_id,
            procedure_id=context.procedure_id,
            procedure_version=context.procedure_version,
            dataset_id=context.dataset_id,
            source_sha256=context.source_sha256,
            mapping_fingerprint=context.mapping_fingerprint,
            audit_period_start=context.audit_period_start,
            audit_period_end=context.audit_period_end,
            audit_currency=context.audit_currency,
            executor=context.executor,
            parameters=context.parameters,
            completed_at=completed_at,
        )

    @classmethod
    def create(
        cls,
        *,
        execution_id: str,
        procedure_id: str,
        procedure_version: str,
        dataset_id: str,
        source_sha256: str,
        mapping_fingerprint: str,
        audit_period_start: str = "",
        audit_period_end: str = "",
        audit_currency: str = "",
        executor: ProcedureExecutorIdentity | None = None,
        parameters: Mapping[str, object] | None = None,
        completed_at: str,
    ) -> ProcedureExecutionStamp:
        """Create and validate a procedure execution stamp."""

        cleaned_execution_id = execution_id.strip()
        cleaned_version = procedure_version.strip()
        cleaned_dataset_id = dataset_id.strip()
        cleaned_completed_at = completed_at.strip()

        if not cleaned_execution_id:
            raise ValueError("Procedure execution identifier is required.")

        if not cleaned_version:
            raise ValueError("Procedure version is required.")

        if not cleaned_dataset_id:
            raise ValueError("Procedure execution dataset identifier is required.")

        if not cleaned_completed_at:
            raise ValueError("Procedure completion time is required.")

        if executor is None:
            cleaned_executor = ProcedureExecutorIdentity()
        elif not isinstance(executor, ProcedureExecutorIdentity):
            raise TypeError("Procedure executor identity must be a ProcedureExecutorIdentity.")
        else:
            cleaned_executor = ProcedureExecutorIdentity.create(
                full_name=executor.full_name,
                job_title=executor.job_title,
                directorate=executor.directorate,
                organization=executor.organization,
            )

        return cls(
            execution_id=cleaned_execution_id,
            procedure_id=canonical_procedure_id(procedure_id),
            procedure_version=cleaned_version,
            dataset_id=cleaned_dataset_id,
            source_sha256=_require_sha256(
                source_sha256,
                label="Source SHA-256",
            ),
            mapping_fingerprint=_require_sha256(
                mapping_fingerprint,
                label="Mapping fingerprint",
            ),
            audit_period_start=audit_period_start.strip(),
            audit_period_end=audit_period_end.strip(),
            audit_currency=normalise_currency_code(audit_currency, allow_blank=True),
            executor=cleaned_executor,
            parameters=normalise_execution_parameters(parameters or {}),
            completed_at=cleaned_completed_at,
        )

    @classmethod
    def from_dict(
        cls,
        raw: Mapping[str, object],
    ) -> ProcedureExecutionStamp:
        """Restore one execution stamp from saved workspace data."""

        parameters = raw.get("parameters", {})
        raw_executor = raw.get("executor", {})

        if not isinstance(parameters, Mapping):
            raise TypeError("Procedure execution parameters must be an object.")
        if not isinstance(raw_executor, Mapping):
            raise TypeError("Procedure executor identity must be an object.")

        executor = ProcedureExecutorIdentity.create(
            full_name=_optional_text(raw_executor.get("full_name")),
            job_title=_optional_text(raw_executor.get("job_title")),
            directorate=_optional_text(raw_executor.get("directorate")),
            organization=_optional_text(raw_executor.get("organization")),
        )

        return cls.create(
            execution_id=str(raw["execution_id"]),
            procedure_id=str(raw["procedure_id"]),
            procedure_version=str(raw["procedure_version"]),
            dataset_id=str(raw["dataset_id"]),
            source_sha256=str(raw["source_sha256"]),
            mapping_fingerprint=str(raw["mapping_fingerprint"]),
            audit_period_start=str(raw.get("audit_period_start", "")),
            audit_period_end=str(raw.get("audit_period_end", "")),
            audit_currency=str(raw.get("audit_currency", "")),
            executor=executor,
            parameters=parameters,
            # Older workspaces may contain the pre-hardening context-creation time here.
            # Preserve the recorded value rather than inventing a historical completion time.
            completed_at=str(raw["completed_at"]),
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible workspace data for this stamp."""

        return {
            "execution_id": self.execution_id,
            "procedure_id": self.procedure_id,
            "procedure_version": self.procedure_version,
            "dataset_id": self.dataset_id,
            "source_sha256": self.source_sha256,
            "mapping_fingerprint": self.mapping_fingerprint,
            "audit_period_start": self.audit_period_start,
            "audit_period_end": self.audit_period_end,
            "audit_currency": self.audit_currency,
            "executor": {
                "full_name": self.executor.full_name,
                "job_title": self.executor.job_title,
                "directorate": self.executor.directorate,
                "organization": self.executor.organization,
            },
            "parameters": normalise_execution_parameters(self.parameters or {}),
            "completed_at": self.completed_at,
        }


def _optional_text(value: object) -> str:
    """Return optional persisted executor text while rejecting malformed values."""

    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("Procedure executor identity values must be text or null.")
    return value


def normalise_execution_parameters(
    parameters: Mapping[str, object],
) -> dict[str, object]:
    """Return deterministic JSON-compatible procedure parameters."""

    if not isinstance(parameters, Mapping):
        raise TypeError("Procedure execution parameters must be a mapping.")

    cleaned: dict[str, object] = {}

    for raw_key, raw_value in parameters.items():
        key = str(raw_key).strip()

        if not key:
            raise ValueError("Procedure execution parameter keys cannot be blank.")

        cleaned[key] = _normalise_value(
            raw_value,
            path=key,
        )

    return cleaned


def _normalise_value(
    value: object,
    *,
    path: str,
) -> object:
    """Normalise one nested parameter value."""

    if value is None or isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _normalise_value(
                item,
                path=f"{path}[]",
            )
            for item in value
        ]

    if isinstance(value, Mapping):
        nested: dict[str, object] = {}

        for raw_key, raw_value in value.items():
            key = str(raw_key).strip()

            if not key:
                raise ValueError("Nested procedure execution parameter keys cannot be blank.")

            nested[key] = _normalise_value(
                raw_value,
                path=f"{path}.{key}",
            )

        return nested

    raise TypeError(
        "Procedure execution parameters must be JSON-compatible. "
        f"Unsupported value at {path}: {type(value).__name__}."
    )


def _require_sha256(
    value: str,
    *,
    label: str,
) -> str:
    """Validate a SHA-256 hexadecimal digest."""

    cleaned = value.strip().lower()

    if len(cleaned) != 64:
        raise ValueError(f"{label} must contain 64 hexadecimal characters.")

    try:
        int(cleaned, 16)
    except ValueError as error:
        raise ValueError(f"{label} must contain only hexadecimal characters.") from error

    return cleaned
