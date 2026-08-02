"""GL-003 Weekend Postings audit-test engine."""

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from auditor_support_tool.domains.financial_audit.general_ledger.field_mapping_service import (
    FieldMappingService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
    LoadedTable,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_definitions import (
    GL_003_WEEKEND_POSTINGS,
)
from auditor_support_tool.domains.financial_audit.general_ledger.test_models import (
    DataQualityIssue,
    FieldMapping,
    TestException,
    TestMetric,
    TestRunResult,
)


class WeekendPostingsTestError(RuntimeError):
    """Raised when GL-003 cannot be executed."""


class WeekendPostingsTest:
    """Identify General Ledger transactions dated on weekends."""

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
        """Execute GL-003 against a loaded General Ledger population."""

        mapping_by_field = self._field_mapping_service.mapping_dictionary(
            table,
            mappings,
        )

        transaction_date_column = mapping_by_field.get("transaction_date")

        if transaction_date_column is None:
            raise WeekendPostingsTestError("GL-003 requires a mapped transaction-date field.")

        exceptions: list[TestException] = []
        data_quality_issues: list[DataQualityIssue] = []

        records_tested = 0
        blank_dates = 0
        invalid_dates = 0
        saturday_postings = 0
        sunday_postings = 0
        weekend_dates: set[date] = set()

        for record in table.rows:
            source_row_number = self._source_row_number(record)
            source_value = record.get(transaction_date_column)

            if self._is_blank_value(source_value):
                blank_dates += 1

                data_quality_issues.append(
                    DataQualityIssue(
                        issue_type="blank_transaction_date",
                        message=("The record was excluded because its transaction date is blank."),
                        source_row_number=source_row_number,
                        source_value=source_value,
                    )
                )
                continue

            parsed_date = self._parse_date(source_value)

            if parsed_date is None:
                invalid_dates += 1

                data_quality_issues.append(
                    DataQualityIssue(
                        issue_type="invalid_transaction_date",
                        message=(
                            "The record was excluded because its "
                            "transaction date could not be interpreted."
                        ),
                        source_row_number=source_row_number,
                        source_value=source_value,
                    )
                )
                continue

            records_tested += 1
            weekday_number = parsed_date.weekday()

            if weekday_number not in {
                5,
                6,
            }:
                continue

            day_name = "Saturday" if weekday_number == 5 else "Sunday"

            if weekday_number == 5:
                saturday_postings += 1
            else:
                sunday_postings += 1

            weekend_dates.add(parsed_date)

            exception_number = len(exceptions) + 1

            exceptions.append(
                TestException(
                    exception_id=f"GL-003-{exception_number:06d}",
                    source_row_number=source_row_number,
                    reason=(f"Weekend posting: {day_name} — further scrutiny required."),
                    source_record=dict(record),
                    derived_values={
                        "parsed_transaction_date": (parsed_date.isoformat()),
                        "day_of_week": day_name,
                        "weekday_number": weekday_number,
                        "weekend_type": "Weekend",
                    },
                )
            )

        records_excluded = blank_dates + invalid_dates
        weekend_postings = len(exceptions)

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
                key="weekend_postings",
                label="Weekend postings",
                value=weekend_postings,
            ),
            TestMetric(
                key="saturday_postings",
                label="Saturday postings",
                value=saturday_postings,
            ),
            TestMetric(
                key="sunday_postings",
                label="Sunday postings",
                value=sunday_postings,
            ),
            TestMetric(
                key="distinct_weekend_dates",
                label="Distinct weekend dates",
                value=len(weekend_dates),
            ),
            TestMetric(
                key="blank_dates",
                label="Blank dates",
                value=blank_dates,
            ),
            TestMetric(
                key="invalid_dates",
                label="Invalid dates",
                value=invalid_dates,
            ),
        )

        return TestRunResult(
            test_code=GL_003_WEEKEND_POSTINGS.code,
            test_title=GL_003_WEEKEND_POSTINGS.title,
            logic_version=GL_003_WEEKEND_POSTINGS.logic_version,
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
                "weekend_days": (
                    "Saturday",
                    "Sunday",
                ),
                "blank_dates_excluded": True,
                "invalid_dates_excluded": True,
                "date_field": transaction_date_column,
            },
        )

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Convert a supported source value into a date."""

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        if not isinstance(value, str):
            return None

        text = value.strip()

        if not text:
            return None

        formats = (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        )

        for format_string in formats:
            try:
                return datetime.strptime(
                    text,
                    format_string,
                ).date()
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None

    @staticmethod
    def _is_blank_value(value: Any) -> bool:
        """Return whether a source date value is blank."""

        if value is None:
            return True

        return isinstance(value, str) and not value.strip()

    @staticmethod
    def _source_row_number(record: dict[str, Any]) -> int:
        """Return and validate the source row number."""

        value = record.get(SOURCE_ROW_FIELD)

        if isinstance(value, bool) or not isinstance(value, int):
            raise WeekendPostingsTestError("A source record has no valid source row number.")

        return value
