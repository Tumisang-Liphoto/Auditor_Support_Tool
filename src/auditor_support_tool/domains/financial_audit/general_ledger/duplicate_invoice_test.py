"""GL-001 Duplicate Invoice Detection audit-test engine."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from auditor_support_tool.domains.financial_audit.general_ledger.field_mapping_service import (
    FieldMappingService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
    LoadedTable,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_definitions import (
    GL_001_DUPLICATE_INVOICES,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    DataQualityIssue,
    FieldMapping,
    TestException,
    TestMetric,
    TestRunResult,
)

EXCEPTION_REASON = "Repeated invoice number — further scrutiny required."


class DuplicateInvoiceTestError(RuntimeError):
    """Raised when GL-001 cannot be executed."""


class DuplicateInvoiceTest:
    """Identify repeated invoice numbers in a loaded population."""

    def __init__(
        self,
        field_mapping_service: FieldMappingService | None = None,
    ) -> None:
        self._field_mapping_service = field_mapping_service or FieldMappingService()

    def run(
        self,
        table: LoadedTable,
        mappings: Iterable[FieldMapping],
    ) -> TestRunResult:
        """Execute GL-001 against a loaded General Ledger population."""

        mapping_by_field = self._field_mapping_service.mapping_dictionary(
            table,
            mappings,
        )

        invoice_column = mapping_by_field.get("invoice_number")

        if invoice_column is None:
            raise DuplicateInvoiceTestError("GL-001 requires a mapped invoice-number field.")

        vendor_column = mapping_by_field.get("vendor_number")
        vendor_name_column = mapping_by_field.get("vendor_name")

        grouped_records: dict[str, list[dict[str, Any]]] = defaultdict(list)

        data_quality_issues: list[DataQualityIssue] = []
        records_tested = 0
        records_excluded = 0

        for record in table.rows:
            source_row_number = self._source_row_number(record)
            original_invoice_number = record.get(invoice_column)

            normalised_invoice_number = self._normalise_invoice_number(original_invoice_number)

            if not normalised_invoice_number:
                records_excluded += 1

                data_quality_issues.append(
                    DataQualityIssue(
                        issue_type="blank_invoice_number",
                        message=("The record was excluded because its invoice number is blank."),
                        source_row_number=source_row_number,
                        source_value=original_invoice_number,
                    )
                )
                continue

            records_tested += 1
            grouped_records[normalised_invoice_number].append(record)

        duplicate_groups = [
            (normalised_invoice_number, records)
            for normalised_invoice_number, records in grouped_records.items()
            if len(records) > 1
        ]

        duplicate_groups.sort(
            key=lambda item: min(self._source_row_number(record) for record in item[1])
        )

        exceptions: list[TestException] = []

        same_vendor_groups = 0
        multiple_vendor_groups = 0
        vendor_not_assessable_groups = 0

        for group_number, (
            normalised_invoice_number,
            records,
        ) in enumerate(
            duplicate_groups,
            start=1,
        ):
            group_id = f"GL-001-GROUP-{group_number:04d}"

            vendor_relationship = self._vendor_relationship(
                records,
                vendor_column=vendor_column,
                vendor_name_column=vendor_name_column,
            )

            if vendor_relationship == "Same vendor":
                same_vendor_groups += 1
            elif vendor_relationship == "Multiple vendors":
                multiple_vendor_groups += 1
            else:
                vendor_not_assessable_groups += 1

            sorted_records = sorted(
                records,
                key=self._source_row_number,
            )

            for record in sorted_records:
                exception_number = len(exceptions) + 1
                source_row_number = self._source_row_number(record)

                exceptions.append(
                    TestException(
                        exception_id=f"GL-001-{exception_number:06d}",
                        source_row_number=source_row_number,
                        reason=EXCEPTION_REASON,
                        source_record=dict(record),
                        derived_values={
                            "normalised_invoice_number": (normalised_invoice_number),
                            "duplicate_group_size": len(records),
                            "vendor_relationship": vendor_relationship,
                        },
                        group_id=group_id,
                    )
                )

        flagged_records = len(exceptions)

        additional_duplicate_records = sum(len(records) - 1 for _, records in duplicate_groups)

        metrics = (
            TestMetric(
                key="population_records",
                label="Population records",
                value=table.record_count,
            ),
            TestMetric(
                key="records_tested",
                label="Records tested",
                value=records_tested,
            ),
            TestMetric(
                key="records_excluded",
                label="Records excluded",
                value=records_excluded,
            ),
            TestMetric(
                key="duplicate_groups",
                label="Repeated invoice groups",
                value=len(duplicate_groups),
            ),
            TestMetric(
                key="flagged_records",
                label="Records flagged",
                value=flagged_records,
            ),
            TestMetric(
                key="additional_duplicate_records",
                label="Additional duplicate records",
                value=additional_duplicate_records,
            ),
            TestMetric(
                key="same_vendor_groups",
                label="Same-vendor groups",
                value=same_vendor_groups,
            ),
            TestMetric(
                key="multiple_vendor_groups",
                label="Multiple-vendor groups",
                value=multiple_vendor_groups,
            ),
            TestMetric(
                key="vendor_not_assessable_groups",
                label="Vendor relationship not assessable",
                value=vendor_not_assessable_groups,
            ),
        )

        return TestRunResult(
            test_code=GL_001_DUPLICATE_INVOICES.code,
            test_title=GL_001_DUPLICATE_INVOICES.title,
            logic_version=GL_001_DUPLICATE_INVOICES.logic_version,
            source_file=table.source_path.name,
            worksheet_name=table.worksheet_name,
            population_records=table.record_count,
            records_tested=records_tested,
            records_excluded=records_excluded,
            executed_at=datetime.now(),
            metrics=metrics,
            exceptions=tuple(exceptions),
            data_quality_issues=tuple(data_quality_issues),
            configuration={
                "duplicate_rule": "Invoice Number",
                "ignore_blank_invoice_numbers": True,
                "trim_leading_and_trailing_spaces": True,
                "case_sensitive": False,
                "vendor_used_as_duplicate_key": False,
            },
        )

    @staticmethod
    def _normalise_invoice_number(value: Any) -> str:
        """Return the comparison form of an invoice number."""

        if value is None:
            return ""

        normalised = str(value).strip()

        if not normalised:
            return ""

        return normalised.casefold()

    @staticmethod
    def _normalise_vendor_value(value: Any) -> str:
        """Return a normalised vendor identifier or name."""

        if value is None:
            return ""

        return str(value).strip().casefold()

    def _vendor_relationship(
        self,
        records: list[dict[str, Any]],
        *,
        vendor_column: str | None,
        vendor_name_column: str | None,
    ) -> str:
        """Describe whether records belong to the same vendor."""

        selected_vendor_column = vendor_column or vendor_name_column

        if selected_vendor_column is None:
            return "Not assessable"

        vendor_values = {
            self._normalise_vendor_value(record.get(selected_vendor_column)) for record in records
        }

        nonblank_vendor_values = {value for value in vendor_values if value}

        if not nonblank_vendor_values:
            return "Not assessable"

        if len(nonblank_vendor_values) == 1:
            if "" in vendor_values:
                return "Not assessable"

            return "Same vendor"

        return "Multiple vendors"

    @staticmethod
    def _source_row_number(record: dict[str, Any]) -> int:
        """Return and validate the source row number."""

        value = record.get(SOURCE_ROW_FIELD)

        if isinstance(value, bool) or not isinstance(value, int):
            raise DuplicateInvoiceTestError("A source record has no valid source row number.")

        return value
