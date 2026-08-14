"""Standard run and result contracts for audit procedures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.workspace_models import utc_now_iso

DEFAULT_AUDIT_USE_STATEMENT = (
    "This procedure identifies records meeting the configured criteria "
    "for auditor review. It does not by itself establish an audit finding."
)


@dataclass(frozen=True, slots=True)
class ProcedureRunContext:
    """Reproducibility context attached to one audit-procedure run."""

    execution_id: str
    procedure_id: str
    procedure_version: str
    dataset_id: str

    source_sha256: str
    mapping_fingerprint: str

    parameters: dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        *,
        request: AuditExecutionRequest,
        procedure_version: str,
        source_sha256: str,
        mapping_fingerprint: str,
        parameters: Mapping[str, object] | None = None,
    ) -> ProcedureRunContext:
        """Create and validate the reproducibility context for a run."""

        cleaned_version = procedure_version.strip()

        if not cleaned_version:
            raise ValueError("Procedure version is required.")

        cleaned_source_hash = _require_sha256(
            source_sha256,
            label="Source SHA-256",
        )
        cleaned_mapping_hash = _require_sha256(
            mapping_fingerprint,
            label="Mapping fingerprint",
        )

        return cls(
            execution_id=request.execution_id,
            procedure_id=request.procedure_id,
            procedure_version=cleaned_version,
            dataset_id=request.dataset_id,
            source_sha256=cleaned_source_hash,
            mapping_fingerprint=cleaned_mapping_hash,
            parameters=dict(parameters or {}),
        )


@dataclass(frozen=True, slots=True)
class ProcedureExceptionRecord:
    """One source-linked record identified by an audit procedure."""

    source_record_id: str
    source_row_number: int
    reason_code: str
    reason: str

    values: dict[str, object] = field(default_factory=dict)
    related_value: Decimal | None = None

    @classmethod
    def create(
        cls,
        *,
        source_record_id: str,
        source_row_number: int,
        reason_code: str,
        reason: str,
        values: Mapping[str, object] | None = None,
        related_value: Decimal | None = None,
    ) -> ProcedureExceptionRecord:
        """Create a validated procedure exception record."""

        cleaned_record_id = source_record_id.strip()
        cleaned_reason_code = reason_code.strip()
        cleaned_reason = reason.strip()

        if not cleaned_record_id:
            raise ValueError("Source record identifier is required.")

        if source_row_number < 1:
            raise ValueError("Source row number must be at least 1.")

        if not cleaned_reason_code:
            raise ValueError("Exception reason code is required.")

        if not cleaned_reason:
            raise ValueError("Exception reason is required.")

        return cls(
            source_record_id=cleaned_record_id,
            source_row_number=source_row_number,
            reason_code=cleaned_reason_code,
            reason=cleaned_reason,
            values=dict(values or {}),
            related_value=related_value,
        )


@dataclass(frozen=True, slots=True)
class ProcedureResult:
    """Standard result returned by every audit procedure."""

    context: ProcedureRunContext

    population_count: int
    records_evaluated_count: int
    excluded_record_count: int

    exception_count: int
    exception_rate: float

    exception_records: tuple[ProcedureExceptionRecord, ...] = ()
    exclusion_counts: dict[str, int] = field(default_factory=dict)

    related_value_total: Decimal | None = None

    limitations: tuple[str, ...] = ()
    metrics: dict[str, object] = field(default_factory=dict)

    audit_use_statement: str = DEFAULT_AUDIT_USE_STATEMENT

    @classmethod
    def create(
        cls,
        *,
        context: ProcedureRunContext,
        population_count: int,
        records_evaluated_count: int,
        exception_records: tuple[ProcedureExceptionRecord, ...] = (),
        exclusion_counts: Mapping[str, int] | None = None,
        related_value_total: Decimal | None = None,
        limitations: tuple[str, ...] = (),
        metrics: Mapping[str, object] | None = None,
        audit_use_statement: str = DEFAULT_AUDIT_USE_STATEMENT,
    ) -> ProcedureResult:
        """Create a validated standard procedure result.

        ``exception_rate`` is stored as a percentage from 0.0 to 100.0 and
        uses only records actually evaluated by the procedure as its
        denominator.
        """

        if population_count < 0:
            raise ValueError("Population count cannot be negative.")

        if records_evaluated_count < 0:
            raise ValueError("Records evaluated count cannot be negative.")

        if records_evaluated_count > population_count:
            raise ValueError("Records evaluated count cannot exceed population count.")

        cleaned_exclusion_counts: dict[str, int] = {}

        for raw_reason, raw_count in (exclusion_counts or {}).items():
            reason = str(raw_reason).strip()

            if not reason:
                raise ValueError("Exclusion reason cannot be blank.")

            count = int(raw_count)

            if count < 0:
                raise ValueError("Exclusion counts cannot be negative.")

            if count:
                cleaned_exclusion_counts[reason] = count

        excluded_record_count = population_count - records_evaluated_count

        if sum(cleaned_exclusion_counts.values()) != excluded_record_count:
            raise ValueError("Exclusion counts must equal the number of records not evaluated.")

        exception_records_tuple = tuple(exception_records)
        exception_count = len(exception_records_tuple)

        if exception_count > records_evaluated_count:
            raise ValueError("Exception count cannot exceed records evaluated.")

        exception_rate = (
            (exception_count / records_evaluated_count) * 100.0 if records_evaluated_count else 0.0
        )

        cleaned_limitations = tuple(
            limitation.strip() for limitation in limitations if limitation.strip()
        )

        cleaned_audit_use_statement = audit_use_statement.strip()

        if not cleaned_audit_use_statement:
            raise ValueError("Audit-use statement cannot be blank.")

        return cls(
            context=context,
            population_count=population_count,
            records_evaluated_count=records_evaluated_count,
            excluded_record_count=excluded_record_count,
            exception_count=exception_count,
            exception_rate=exception_rate,
            exception_records=exception_records_tuple,
            exclusion_counts=cleaned_exclusion_counts,
            related_value_total=related_value_total,
            limitations=cleaned_limitations,
            metrics=dict(metrics or {}),
            audit_use_statement=cleaned_audit_use_statement,
        )


def _require_sha256(
    value: str,
    *,
    label: str,
) -> str:
    """Validate and normalise a SHA-256 hexadecimal digest."""

    cleaned = value.strip().lower()

    if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
        raise ValueError(f"{label} must be a valid SHA-256 digest.")

    return cleaned
