"""Tests for prepared audit-dataset resolution and traceability."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from auditor_support_tool.core.data_profile_models import (
    DetectedDataType,
)
from auditor_support_tool.core.prepared_audit_dataset import (
    FieldValueStatus,
    PreparedAuditDataset,
    PreparedAuditDatasetError,
    build_source_record_id,
    calculate_mapping_fingerprint,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD,
)


def create_dataset(
    tmp_path: Path,
):
    """Create a small General Ledger dataset with a skipped blank row."""

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "General_Ledger"

    worksheet.append(
        [
            "Trn Dt",
            "Account No",
            "Amount",
            "Narrative",
        ]
    )
    worksheet.append(
        [
            "2026-01-03",
            "1000",
            125.50,
            "Weekend payment",
        ]
    )
    worksheet.append(
        [
            None,
            None,
            None,
            None,
        ]
    )
    worksheet.append(
        [
            "2026-01-05",
            "2000",
            250.00,
            "",
        ]
    )

    path = tmp_path / "prepared-audit-dataset.xlsx"
    workbook.save(path)

    package = WorkbookPackageService().build_package(path)
    dataset = package.get_dataset_by_worksheet("General_Ledger")

    assert dataset is not None

    date_column = next(column for column in dataset.columns if column.source_column == "Trn Dt")
    account_column = next(
        column for column in dataset.columns if column.source_column == "Account No"
    )
    amount_column = next(column for column in dataset.columns if column.source_column == "Amount")
    narrative_column = next(
        column for column in dataset.columns if column.source_column == "Narrative"
    )

    date_column.confirmed_type = DetectedDataType.DATE
    account_column.confirmed_type = DetectedDataType.TEXT
    amount_column.confirmed_type = DetectedDataType.DECIMAL
    narrative_column.confirmed_type = DetectedDataType.TEXT

    dataset.field_mappings = {
        date_column.column_id: "transaction_date",
        account_column.column_id: "account_code",
        amount_column.column_id: "transaction_amount",
        narrative_column.column_id: "transaction_description",
    }

    return (
        dataset,
        date_column,
        account_column,
        amount_column,
        narrative_column,
    )


def test_imported_rows_retain_actual_source_row_numbers(
    tmp_path: Path,
) -> None:
    """Skipped blank rows must not destroy original source-row identity."""

    dataset, *_columns = create_dataset(tmp_path)

    assert [row[SOURCE_ROW_FIELD] for row in dataset.loaded_table.rows] == [2, 4]


def test_source_record_identity_is_stable_and_dataset_scoped() -> None:
    """A source record ID should combine dataset ID and source row number."""

    assert (
        build_source_record_id(
            "dataset-abc",
            417,
        )
        == "dataset-abc:row-417"
    )


def test_iter_records_preserves_raw_rows_without_population_copy(
    tmp_path: Path,
) -> None:
    """Prepared records should wrap the existing source dictionaries."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)

    first_record = next(prepared.iter_records())

    assert first_record.raw_row is dataset.loaded_table.rows[0]
    assert first_record.source_row_number == 2
    assert first_record.source_record_id == (f"{dataset.dataset_id}:row-2")


def test_standard_field_resolves_auditee_specific_source_column(
    tmp_path: Path,
) -> None:
    """Procedures should read standard fields, not source column names."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    date_value = first_record.resolve("transaction_date")
    account_value = first_record.resolve("account_code")
    amount_value = first_record.resolve("transaction_amount")

    assert date_value.status == FieldValueStatus.VALID
    assert date_value.value == date(2026, 1, 3)

    assert account_value.status == FieldValueStatus.VALID
    assert account_value.value == "1000"

    assert amount_value.status == FieldValueStatus.VALID
    assert str(amount_value.value) == "125.5"


def test_prepared_name_change_does_not_break_standard_field_access(
    tmp_path: Path,
) -> None:
    """Field resolution must depend on stable mapping, not visible prepared name."""

    dataset, date_column, *_columns = create_dataset(tmp_path)

    date_column.confirmed_name = "Posting / Transaction Date"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.source_column == "Trn Dt"
    assert resolved.column_id == date_column.column_id


def test_blank_mapped_value_is_reported_separately(
    tmp_path: Path,
) -> None:
    """Blank values should not be silently treated as valid values."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)

    records = list(prepared.iter_records())
    second_record = records[1]

    resolved = second_record.resolve("transaction_description")

    assert resolved.status == FieldValueStatus.BLANK
    assert resolved.value is None


def test_invalid_date_is_reported_as_invalid(
    tmp_path: Path,
) -> None:
    """Invalid typed values should be distinguishable from blanks."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = "not-a-date"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None
    assert resolved.reason


def test_unmapped_field_is_reported_without_exception(
    tmp_path: Path,
) -> None:
    """Value-adding fields may be absent without breaking record access."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("entry_user")

    assert resolved.status == FieldValueStatus.UNMAPPED
    assert resolved.value is None


def test_mapping_fingerprint_is_deterministic(
    tmp_path: Path,
) -> None:
    """Unchanged mappings should always produce the same fingerprint."""

    dataset, *_columns = create_dataset(tmp_path)

    first = calculate_mapping_fingerprint(dataset)
    second = calculate_mapping_fingerprint(dataset)

    assert first == second
    assert len(first) == 64


def test_mapping_fingerprint_changes_when_mapping_changes(
    tmp_path: Path,
) -> None:
    """Mapping changes must produce a new version fingerprint."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    original = calculate_mapping_fingerprint(dataset)

    dataset.field_mappings[account_column.column_id] = "vendor_code"

    changed = calculate_mapping_fingerprint(dataset)

    assert changed != original


def test_mapping_fingerprint_changes_when_confirmed_type_changes(
    tmp_path: Path,
) -> None:
    """A type decision affects the mapping/version used by procedures."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    original = calculate_mapping_fingerprint(dataset)

    account_column.confirmed_type = DetectedDataType.INTEGER

    changed = calculate_mapping_fingerprint(dataset)

    assert changed != original

def test_unknown_mapped_column_is_rejected(
    tmp_path: Path,
) -> None:
    """Mappings must never reference a prepared column that no longer exists."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.field_mappings["missing-column-id"] = "vendor_code"

    with pytest.raises(
        PreparedAuditDatasetError,
        match="unknown prepared column",
    ):
        PreparedAuditDataset(dataset)


def test_excluded_mapped_column_is_rejected(
    tmp_path: Path,
) -> None:
    """An excluded source column must never remain available to procedures."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    account_column.included = False

    with pytest.raises(
        PreparedAuditDatasetError,
        match="excluded prepared column",
    ):
        PreparedAuditDataset(dataset)


def test_standard_field_cannot_be_mapped_from_multiple_columns(
    tmp_path: Path,
) -> None:
    """A standard field must resolve to exactly one source column."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    dataset.field_mappings[
        account_column.column_id
    ] = "transaction_date"

    with pytest.raises(
        PreparedAuditDatasetError,
        match="mapped more than once",
    ):
        PreparedAuditDataset(dataset)


@pytest.mark.parametrize(
    "source_row_number",
    (
        True,
        None,
        0,
        -1,
        "not-a-row-number",
    ),
)
def test_invalid_source_row_identity_is_rejected(
    tmp_path: Path,
    source_row_number,
) -> None:
    """Source traceability must fail closed when row identity is corrupt."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0][SOURCE_ROW_FIELD] = source_row_number

    prepared = PreparedAuditDataset(dataset)

    with pytest.raises(
        PreparedAuditDatasetError,
        match="source row number",
    ):
        next(prepared.iter_records())


def test_missing_mapped_source_column_is_reported_as_invalid(
    tmp_path: Path,
) -> None:
    """A mapped column missing from an individual source row is invalid."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0].pop("Amount")

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_amount")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None
    assert resolved.raw_value is None
    assert resolved.source_column == "Amount"
    assert "missing from the source record" in resolved.reason


def test_boolean_cannot_be_interpreted_as_decimal_amount(
    tmp_path: Path,
) -> None:
    """Boolean values must not silently become numeric audit amounts."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Amount"] = True

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_amount")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None
    assert "Boolean values cannot be interpreted as amounts" in resolved.reason


def test_integer_conversion_accepts_grouped_whole_number(
    tmp_path: Path,
) -> None:
    """A whole-number string should resolve without losing meaning."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    account_column.confirmed_type = DetectedDataType.INTEGER
    dataset.loaded_table.rows[0]["Account No"] = "1,250"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("account_code")

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == 1250


def test_integer_conversion_rejects_fractional_value(
    tmp_path: Path,
) -> None:
    """Integer conversion must never silently round a fractional source value."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    account_column.confirmed_type = DetectedDataType.INTEGER
    dataset.loaded_table.rows[0]["Account No"] = "1250.5"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("account_code")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None
    assert "not a whole number" in resolved.reason


def test_ambiguous_day_month_date_is_rejected(
    tmp_path: Path,
) -> None:
    """Ambiguous numeric dates must not be guessed by audit procedures."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = "01/02/2026"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None
    assert "unambiguous date" in resolved.reason


@pytest.mark.parametrize(
    ("source_value", "expected"),
    (
        ("13/02/2026", date(2026, 2, 13)),
        ("02/13/2026", date(2026, 2, 13)),
    ),
)
def test_unambiguous_numeric_date_is_resolved(
    tmp_path: Path,
    source_value: str,
    expected: date,
) -> None:
    """Numeric dates may be used only where day/month order is unambiguous."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = source_value

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == expected


def test_iso_datetime_with_timezone_is_resolved(
    tmp_path: Path,
) -> None:
    """ISO timestamps should retain their explicit timezone information."""

    dataset, date_column, *_columns = create_dataset(tmp_path)

    date_column.confirmed_type = DetectedDataType.DATETIME
    dataset.loaded_table.rows[0]["Trn Dt"] = "2026-01-03T10:15:00Z"

    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    resolved = first_record.resolve("transaction_date")

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == datetime.fromisoformat(
        "2026-01-03T10:15:00+00:00"
    )


def test_source_record_id_rejects_invalid_identity() -> None:
    """Stable source-record IDs require both dataset and row identity."""

    with pytest.raises(
        ValueError,
        match="Dataset identifier is required",
    ):
        build_source_record_id(
            "   ",
            2,
        )

    with pytest.raises(
        ValueError,
        match="Source row number must be at least 1",
    ):
        build_source_record_id(
            "dataset-abc",
            0,
        )

def test_blank_standard_field_key_is_rejected(
    tmp_path: Path,
) -> None:
    """Procedure code must identify the standard field it wants to resolve."""

    dataset, *_columns = create_dataset(tmp_path)
    prepared = PreparedAuditDataset(dataset)
    first_record = next(prepared.iter_records())

    with pytest.raises(
        ValueError,
        match="Standard field key is required",
    ):
        first_record.resolve("   ")


def test_blank_field_mapping_is_ignored(
    tmp_path: Path,
) -> None:
    """Blank mapping entries must not become available standard fields."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    dataset.field_mappings[account_column.column_id] = "   "

    prepared = PreparedAuditDataset(dataset)

    assert not prepared.has_field("account_code")
    assert prepared.column_for_field("account_code") is None


def test_mapping_fingerprint_rejects_unknown_column(
    tmp_path: Path,
) -> None:
    """A fingerprint must not be generated from a stale mapping."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.field_mappings["missing-column-id"] = "vendor_code"

    with pytest.raises(
        PreparedAuditDatasetError,
        match="Cannot fingerprint.*unknown column",
    ):
        calculate_mapping_fingerprint(dataset)


@pytest.mark.parametrize(
    ("source_value", "expected"),
    (
        (1250, 1250),
        (Decimal("1250"), 1250),
        (1250.0, 1250),
    ),
)
def test_integer_conversion_accepts_exact_numeric_values(
    tmp_path: Path,
    source_value,
    expected: int,
) -> None:
    """Exact numeric values should convert without rounding."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    account_column.confirmed_type = DetectedDataType.INTEGER
    dataset.loaded_table.rows[0]["Account No"] = source_value

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve("account_code")

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == expected


@pytest.mark.parametrize(
    "source_value",
    (
        True,
        Decimal("1250.5"),
        1250.5,
    ),
)
def test_integer_conversion_rejects_non_integral_numeric_values(
    tmp_path: Path,
    source_value,
) -> None:
    """Integer fields must never silently round source values."""

    dataset, _date, account_column, *_columns = create_dataset(tmp_path)

    account_column.confirmed_type = DetectedDataType.INTEGER
    dataset.loaded_table.rows[0]["Account No"] = source_value

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve("account_code")

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None


@pytest.mark.parametrize(
    ("source_value", "expected"),
    (
        (Decimal("125.50"), Decimal("125.50")),
        ("1,250.50", Decimal("1250.50")),
    ),
)
def test_decimal_conversion_accepts_decimal_and_text_values(
    tmp_path: Path,
    source_value,
    expected: Decimal,
) -> None:
    """Audit amounts should resolve to Decimal without float coercion."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Amount"] = source_value

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_amount"
    )

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == expected


def test_invalid_decimal_text_is_reported_as_invalid(
    tmp_path: Path,
) -> None:
    """Malformed monetary text must not reach procedure calculations."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Amount"] = "not-an-amount"

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_amount"
    )

    assert resolved.status == FieldValueStatus.INVALID
    assert resolved.value is None


@pytest.mark.parametrize(
    ("source_value", "expected"),
    (
        (
            datetime(2026, 2, 13, 10, 30),
            date(2026, 2, 13),
        ),
        (
            date(2026, 2, 13),
            date(2026, 2, 13),
        ),
    ),
)
def test_date_conversion_accepts_native_date_values(
    tmp_path: Path,
    source_value,
    expected: date,
) -> None:
    """Native spreadsheet date values should remain deterministic."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = source_value

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_date"
    )

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == expected


def test_date_conversion_rejects_non_date_scalar(
    tmp_path: Path,
) -> None:
    """Arbitrary scalar values must not be guessed as dates."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = 20260103

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_date"
    )

    assert resolved.status == FieldValueStatus.INVALID
    assert "cannot be interpreted as a date" in resolved.reason


@pytest.mark.parametrize(
    ("source_value", "expected"),
    (
        (
            datetime(2026, 2, 13, 10, 30),
            datetime(2026, 2, 13, 10, 30),
        ),
        (
            date(2026, 2, 13),
            datetime(2026, 2, 13),
        ),
        (
            "13/02/2026",
            datetime(2026, 2, 13),
        ),
    ),
)
def test_datetime_conversion_accepts_safe_forms(
    tmp_path: Path,
    source_value,
    expected: datetime,
) -> None:
    """Datetime resolution should support native and unambiguous values."""

    dataset, date_column, *_columns = create_dataset(tmp_path)

    date_column.confirmed_type = DetectedDataType.DATETIME
    dataset.loaded_table.rows[0]["Trn Dt"] = source_value

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_date"
    )

    assert resolved.status == FieldValueStatus.VALID
    assert resolved.value == expected


def test_datetime_conversion_rejects_non_datetime_scalar(
    tmp_path: Path,
) -> None:
    """Arbitrary numeric values must not become timestamps."""

    dataset, date_column, *_columns = create_dataset(tmp_path)

    date_column.confirmed_type = DetectedDataType.DATETIME
    dataset.loaded_table.rows[0]["Trn Dt"] = 20260103

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_date"
    )

    assert resolved.status == FieldValueStatus.INVALID
    assert "cannot be interpreted as a datetime" in resolved.reason


def test_two_digit_year_date_is_rejected(
    tmp_path: Path,
) -> None:
    """Short-year numeric dates must not be interpreted heuristically."""

    dataset, *_columns = create_dataset(tmp_path)

    dataset.loaded_table.rows[0]["Trn Dt"] = "13/02/26"

    prepared = PreparedAuditDataset(dataset)
    resolved = next(prepared.iter_records()).resolve(
        "transaction_date"
    )

    assert resolved.status == FieldValueStatus.INVALID
