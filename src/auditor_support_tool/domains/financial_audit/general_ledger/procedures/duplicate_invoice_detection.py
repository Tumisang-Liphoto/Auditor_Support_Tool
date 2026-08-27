"""GL-001 Duplicate Invoice Detection procedure."""

from __future__ import annotations

from dataclasses import dataclass, field

from auditor_support_tool.core.audit_execution_models import (
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureExceptionRecord,
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecord,
    AuditRecordSource,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    FieldValueStatus,
    ResolvedFieldValue,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)

_GL001_DEFINITION = require_general_ledger_procedure("GL001").definition

_REASON_CODE = "DUPLICATE_INVOICE_NUMBER"
_REASON_TEXT = "Repeated invoice number — further audit scrutiny required."

_SAME_VENDOR = "Same vendor"
_MULTIPLE_VENDORS = "Multiple vendors"
_NOT_ASSESSABLE = "Not assessable"


@dataclass(slots=True)
class _InvoiceGroupStats:
    """Lightweight first-pass statistics for one normalised invoice number."""

    count: int = 0
    first_source_row: int = 0

    vendor_codes: set[str] = field(default_factory=set)
    vendor_names: set[str] = field(default_factory=set)

    vendor_code_complete: bool = True
    vendor_name_complete: bool = True


class DuplicateInvoiceDetectionProcedure:
    """Identify repeated nonblank invoice numbers in the complete population."""

    @property
    def definition(self) -> ProcedureDefinition:
        """Return the authoritative GL-001 definition."""

        return _GL001_DEFINITION

    def run(
        self,
        *,
        context: ProcedureRunContext,
        source: AuditRecordSource,
        cancellation_token: ExecutionCancellationToken,
    ) -> ProcedureResult:
        """Execute GL-001 using the approved version 1.0 duplicate rule."""

        groups: dict[str, _InvoiceGroupStats] = {}

        blank_invoice_numbers = 0
        invalid_invoice_numbers = 0
        records_evaluated = 0

        vendor_field_availability: dict[str, bool] | None = None

        # First pass: count invoice numbers and retain only lightweight
        # information needed to characterise duplicate groups.
        for record in source.iter_records():
            cancellation_token.raise_if_cancelled()

            if vendor_field_availability is None:
                vendor_field_availability = self._vendor_field_availability(record)

            resolved_invoice = record.resolve("invoice_number")

            if resolved_invoice.status == FieldValueStatus.BLANK:
                blank_invoice_numbers += 1
                continue

            if resolved_invoice.status != FieldValueStatus.VALID:
                invalid_invoice_numbers += 1
                continue

            normalised_invoice = self._normalise_invoice_number(resolved_invoice.value)

            if not normalised_invoice:
                blank_invoice_numbers += 1
                continue

            records_evaluated += 1

            group = groups.get(normalised_invoice)

            if group is None:
                group = _InvoiceGroupStats(first_source_row=record.source_row_number)
                groups[normalised_invoice] = group

            group.count += 1

            self._capture_vendor_values(
                group=group,
                record=record,
                availability=vendor_field_availability,
            )

        if vendor_field_availability is None:
            vendor_field_availability = {
                "vendor_code": False,
                "vendor_name": False,
            }

        duplicate_keys = tuple(
            key
            for key, _group in sorted(
                ((key, group) for key, group in groups.items() if group.count >= 2),
                key=lambda item: item[1].first_source_row,
            )
        )

        duplicate_key_set = frozenset(duplicate_keys)

        group_ids = {
            key: f"GL-001-GROUP-{index:04d}"
            for index, key in enumerate(
                duplicate_keys,
                start=1,
            )
        }

        vendor_relationships = {
            key: self._vendor_relationship(
                groups[key],
                vendor_field_availability,
            )
            for key in duplicate_keys
        }

        same_vendor_groups = sum(
            1 for relationship in vendor_relationships.values() if relationship == _SAME_VENDOR
        )
        multiple_vendor_groups = sum(
            1 for relationship in vendor_relationships.values() if relationship == _MULTIPLE_VENDORS
        )
        vendor_not_assessable_groups = sum(
            1 for relationship in vendor_relationships.values() if relationship == _NOT_ASSESSABLE
        )

        same_vendor_records = sum(
            groups[key].count for key in duplicate_keys if vendor_relationships[key] == _SAME_VENDOR
        )
        multiple_vendor_records = sum(
            groups[key].count
            for key in duplicate_keys
            if vendor_relationships[key] == _MULTIPLE_VENDORS
        )
        vendor_not_assessable_records = sum(
            groups[key].count
            for key in duplicate_keys
            if vendor_relationships[key] == _NOT_ASSESSABLE
        )

        exceptions: list[ProcedureExceptionRecord] = []

        # Second pass: materialise only records belonging to duplicate groups.
        for record in source.iter_records():
            cancellation_token.raise_if_cancelled()

            resolved_invoice = record.resolve("invoice_number")

            if resolved_invoice.status != FieldValueStatus.VALID:
                continue

            normalised_invoice = self._normalise_invoice_number(resolved_invoice.value)

            if not normalised_invoice or normalised_invoice not in duplicate_key_set:
                continue

            group = groups[normalised_invoice]
            relationship = vendor_relationships[normalised_invoice]

            resolved_helpful = {
                field_key: record.resolve(field_key) for field_key in self.definition.helpful_fields
            }

            exceptions.append(
                ProcedureExceptionRecord.create(
                    source_record_id=record.source_record_id,
                    source_row_number=record.source_row_number,
                    reason_code=_REASON_CODE,
                    reason=_REASON_TEXT,
                    values=self._exception_values(
                        resolved_invoice=resolved_invoice,
                        resolved_helpful=resolved_helpful,
                        normalised_invoice=normalised_invoice,
                        group_id=group_ids[normalised_invoice],
                        group_size=group.count,
                        vendor_relationship=relationship,
                    ),
                )
            )

        exclusion_counts: dict[str, int] = {}

        if blank_invoice_numbers:
            exclusion_counts["blank_invoice_number"] = blank_invoice_numbers

        if invalid_invoice_numbers:
            exclusion_counts["invalid_invoice_number"] = invalid_invoice_numbers

        duplicate_group_count = len(duplicate_keys)
        additional_duplicate_records = sum(groups[key].count - 1 for key in duplicate_keys)

        vendor_analysis_available = bool(
            vendor_field_availability.get("vendor_code")
            or vendor_field_availability.get("vendor_name")
        )

        limitations = self._limitations(
            vendor_analysis_available=vendor_analysis_available,
            invalid_invoice_numbers=invalid_invoice_numbers,
        )

        return ProcedureResult.create(
            context=context,
            population_count=source.record_count,
            records_evaluated_count=records_evaluated,
            exception_records=tuple(exceptions),
            exclusion_counts=exclusion_counts,
            limitations=limitations,
            metrics={
                "duplicate_groups": duplicate_group_count,
                "flagged_records": len(exceptions),
                "additional_duplicate_records": additional_duplicate_records,
                "blank_invoice_number_count": blank_invoice_numbers,
                "invalid_invoice_number_count": invalid_invoice_numbers,
                "vendor_analysis_available": vendor_analysis_available,
                "same_vendor_groups": same_vendor_groups,
                "multiple_vendor_groups": multiple_vendor_groups,
                "vendor_not_assessable_groups": vendor_not_assessable_groups,
                "same_vendor_records": same_vendor_records,
                "multiple_vendor_records": multiple_vendor_records,
                "vendor_not_assessable_records": vendor_not_assessable_records,
            },
        )

    @staticmethod
    def _normalise_invoice_number(
        value: object | None,
    ) -> str:
        """Return the version 1.0 invoice comparison value."""

        if value is None:
            return ""

        text = str(value).strip()

        if not text:
            return ""

        return text.casefold()

    @staticmethod
    def _normalise_vendor_value(
        value: object | None,
    ) -> str:
        """Return a case-insensitive vendor comparison value."""

        if value is None:
            return ""

        return str(value).strip().casefold()

    @staticmethod
    def _vendor_field_availability(
        record: AuditRecord,
    ) -> dict[str, bool]:
        """Return structural availability of vendor context fields."""

        return {
            field_key: (record.resolve(field_key).status != FieldValueStatus.UNMAPPED)
            for field_key in (
                "vendor_code",
                "vendor_name",
            )
        }

    def _capture_vendor_values(
        self,
        *,
        group: _InvoiceGroupStats,
        record: AuditRecord,
        availability: dict[str, bool],
    ) -> None:
        """Capture vendor values needed to classify one invoice group."""

        if availability.get("vendor_code"):
            vendor_code = self._resolved_text(record.resolve("vendor_code"))

            if vendor_code is None:
                group.vendor_code_complete = False
            else:
                group.vendor_codes.add(self._normalise_vendor_value(vendor_code))
        else:
            group.vendor_code_complete = False

        if availability.get("vendor_name"):
            vendor_name = self._resolved_text(record.resolve("vendor_name"))

            if vendor_name is None:
                group.vendor_name_complete = False
            else:
                group.vendor_names.add(self._normalise_vendor_value(vendor_name))
        else:
            group.vendor_name_complete = False

    @staticmethod
    def _vendor_relationship(
        group: _InvoiceGroupStats,
        availability: dict[str, bool],
    ) -> str:
        """Describe the vendor relationship of one duplicate group."""

        if availability.get("vendor_code") and group.vendor_code_complete and group.vendor_codes:
            return _SAME_VENDOR if len(group.vendor_codes) == 1 else _MULTIPLE_VENDORS

        if availability.get("vendor_name") and group.vendor_name_complete and group.vendor_names:
            return _SAME_VENDOR if len(group.vendor_names) == 1 else _MULTIPLE_VENDORS

        return _NOT_ASSESSABLE

    def _exception_values(
        self,
        *,
        resolved_invoice: ResolvedFieldValue,
        resolved_helpful: dict[str, ResolvedFieldValue],
        normalised_invoice: str,
        group_id: str,
        group_size: int,
        vendor_relationship: str,
    ) -> dict[str, object]:
        """Return source-linked values useful for duplicate review."""

        invoice_value = self._resolved_text(resolved_invoice) or ""

        values: dict[str, object] = {
            "invoice_number": invoice_value,
            "normalised_invoice_number": normalised_invoice,
            "duplicate_group_id": group_id,
            "duplicate_group_size": group_size,
            "vendor_relationship": vendor_relationship,
        }

        for field_key in self.definition.helpful_fields:
            resolved = resolved_helpful[field_key]

            if resolved.is_usable:
                values[field_key] = resolved.value

        return values

    @staticmethod
    def _resolved_text(
        resolved: ResolvedFieldValue | None,
    ) -> str | None:
        """Return trimmed text from one usable resolved value."""

        if resolved is None or not resolved.is_usable:
            return None

        text = str(resolved.value).strip()

        return text or None

    @staticmethod
    def _limitations(
        *,
        vendor_analysis_available: bool,
        invalid_invoice_numbers: int,
    ) -> tuple[str, ...]:
        """Return transparent GL-001 execution limitations."""

        limitations: list[str] = []

        if not vendor_analysis_available:
            limitations.append(
                "Vendor Code and Vendor Name are not mapped; "
                "vendor relationship analysis is unavailable."
            )

        if invalid_invoice_numbers:
            limitations.append(
                f"{invalid_invoice_numbers:,} invoice-number record"
                + ("" if invalid_invoice_numbers == 1 else "s")
                + " could not be interpreted and were excluded from evaluation."
            )

        return tuple(limitations)
