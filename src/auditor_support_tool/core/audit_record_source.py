"""Streaming-ready contracts for audit-procedure record access.

Audit procedures should depend on these contracts rather than on a concrete
in-memory table representation. The current PreparedAuditDataset and
PreparedAuditRecord implementations satisfy these contracts structurally,
while future implementations may stream records from other sources.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any, Protocol, runtime_checkable

from auditor_support_tool.core.prepared_audit_dataset import (
    ResolvedFieldValue,
)


@runtime_checkable
class AuditRecord(Protocol):
    """One audit record exposed through standard audit fields."""

    @property
    def raw_row(self) -> Mapping[str, Any]:
        """Return the underlying source record for traceability."""

        ...

    @property
    def source_row_number(self) -> int:
        """Return the original source row number."""

        ...

    @property
    def source_record_id(self) -> str:
        """Return the stable identifier for this source record."""

        ...

    def resolve(
        self,
        standard_field_key: str,
    ) -> ResolvedFieldValue:
        """Resolve one standard audit field."""

        ...

    def value(
        self,
        standard_field_key: str,
        default: object | None = None,
    ) -> object | None:
        """Return a usable standard-field value or the supplied default."""

        ...


@runtime_checkable
class AuditRecordSource(Protocol):
    """Record-access boundary used by audit procedure execution.

    Implementations may keep records in memory or obtain them lazily from a
    streaming source. Audit procedures should therefore iterate through
    ``iter_records`` rather than assume that a ``rows`` collection exists.
    """

    @property
    def dataset_id(self) -> str:
        """Return the stable dataset identifier."""

        ...

    @property
    def record_count(self) -> int:
        """Return the complete source population count."""

        ...

    @property
    def standard_fields(self) -> tuple[str, ...]:
        """Return the available mapped standard audit fields."""

        ...

    @property
    def mapping_fingerprint(self) -> str:
        """Return the deterministic field-mapping fingerprint."""

        ...

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        """Return whether a standard audit field is available."""

        ...

    def iter_records(self) -> Iterator[AuditRecord]:
        """Yield audit records without requiring an in-memory rows collection."""

        ...
