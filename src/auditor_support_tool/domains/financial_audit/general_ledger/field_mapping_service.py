"""Field-mapping and test-availability services for General Ledger analytics."""

from collections.abc import Iterable

from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_definitions import (
    GENERAL_LEDGER_FIELDS,
    GENERAL_LEDGER_TESTS,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    FieldMapping,
    TestAvailability,
    TestAvailabilityStatus,
    TestDefinition,
)


class FieldMappingError(ValueError):
    """Raised when a proposed field mapping is invalid."""


class FieldMappingService:
    """Validate mappings and determine which audit tests can run."""

    def validate_mappings(
        self,
        table: LoadedTable,
        mappings: Iterable[FieldMapping],
    ) -> tuple[FieldMapping, ...]:
        """Validate and normalise mappings for a loaded population."""

        mapping_list = tuple(mappings)

        known_standard_fields = {field_definition.key for field_definition in GENERAL_LEDGER_FIELDS}
        source_columns = set(table.headers)

        seen_standard_fields: set[str] = set()
        seen_source_columns: set[str] = set()
        validated: list[FieldMapping] = []

        for mapping in mapping_list:
            standard_field = mapping.standard_field.strip()
            source_column = mapping.source_column.strip()

            if not standard_field:
                raise FieldMappingError("A mapping contains a blank standard field.")

            if not source_column:
                raise FieldMappingError(
                    f"The mapping for '{standard_field}' has a blank source column."
                )

            if standard_field not in known_standard_fields:
                raise FieldMappingError(f"Unknown standard field: {standard_field}")

            if source_column not in source_columns:
                raise FieldMappingError(f"Source column not found: {source_column}")

            if standard_field in seen_standard_fields:
                raise FieldMappingError(f"Standard field mapped more than once: {standard_field}")

            if source_column in seen_source_columns:
                raise FieldMappingError(f"Source column mapped more than once: {source_column}")

            seen_standard_fields.add(standard_field)
            seen_source_columns.add(source_column)

            validated.append(
                FieldMapping(
                    standard_field=standard_field,
                    source_column=source_column,
                )
            )

        return tuple(validated)

    def mapping_dictionary(
        self,
        table: LoadedTable,
        mappings: Iterable[FieldMapping],
    ) -> dict[str, str]:
        """Return mappings as standard-field to source-column pairs."""

        validated = self.validate_mappings(table, mappings)

        return {mapping.standard_field: mapping.source_column for mapping in validated}

    def check_test_availability(
        self,
        table: LoadedTable,
        mappings: Iterable[FieldMapping],
        test_definition: TestDefinition,
    ) -> TestAvailability:
        """Determine whether an audit test can run."""

        mapping_by_field = self.mapping_dictionary(
            table,
            mappings,
        )

        mapped_required_fields = tuple(
            field_key
            for field_key in test_definition.required_fields
            if field_key in mapping_by_field
        )

        missing_required_fields = tuple(
            field_key
            for field_key in test_definition.required_fields
            if field_key not in mapping_by_field
        )

        mapped_helpful_fields = tuple(
            field_key
            for field_key in test_definition.helpful_fields
            if field_key in mapping_by_field
        )

        warnings: list[str] = []

        if missing_required_fields:
            status = TestAvailabilityStatus.UNAVAILABLE
        elif test_definition.helpful_fields and not mapped_helpful_fields:
            status = TestAvailabilityStatus.AVAILABLE_WITH_WARNING
            warnings.append("The test can run, but no helpful supporting fields are mapped.")
        else:
            status = TestAvailabilityStatus.AVAILABLE

        return TestAvailability(
            test_code=test_definition.code,
            status=status,
            mapped_required_fields=mapped_required_fields,
            missing_required_fields=missing_required_fields,
            mapped_helpful_fields=mapped_helpful_fields,
            warnings=tuple(warnings),
        )

    def check_all_tests(
        self,
        table: LoadedTable,
        mappings: Iterable[FieldMapping],
    ) -> tuple[TestAvailability, ...]:
        """Return availability results for all registered tests."""

        validated_mappings = self.validate_mappings(
            table,
            mappings,
        )

        return tuple(
            self.check_test_availability(
                table,
                validated_mappings,
                test_definition,
            )
            for test_definition in GENERAL_LEDGER_TESTS
        )
