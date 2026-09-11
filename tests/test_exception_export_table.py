"""Complete detached exception projection and value fidelity."""

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest

from auditor_support_tool.presentation.exception_export_table import build_exception_export_table
from tests.test_audit_procedure_report import _result


def export_result():
    result = _result()
    result.exception_records[0].values.update(
        {
            "source_record_id": "0000123",
            "formula": "  =SUM(A1:A2)",
            "negative_number": Decimal("-12.30"),
            "negative_string": "-12.30",
            "nested": {"z": [1, "é"], "a": True},
            "quoted": 'é, "quoted"\nline',
            "null": None,
        }
    )
    result.exception_records[1].values["later"] = "second"
    return result


def test_complete_detached_projection():
    result = export_result()
    original = deepcopy(result)
    table = build_exception_export_table(result)
    assert len(table.rows) == result.exception_count
    assert table.headers[:6] == (
        "dataset_id",
        "source_record_id",
        "source_row_number",
        "procedure_id",
        "procedure_version",
        "execution_id",
    )
    assert len(table.headers) == len(set(table.headers))
    keys = tuple(dict.fromkeys(k for r in result.exception_records for k in r.values))
    assert table.headers[6:-5] == tuple("value." + k for k in keys)
    assert [row[1:3] for row in table.rows] == [
        (r.source_record_id, r.source_row_number) for r in result.exception_records
    ]
    assert table.rows[0][table.headers.index("value.nested")] == '{"a":true,"z":[1,"é"]}'
    assert result == original
    result.exception_records[0].values["nested"]["z"].append(99)
    assert "99" not in table.rows[0][table.headers.index("value.nested")]
    assert dict(table.metadata)["export_scope"] == "All Exceptions"


@pytest.mark.parametrize(
    "value", [object(), float("nan"), Decimal("Infinity"), {"x": float("inf")}]
)
def test_unsupported_values_rejected(value):
    result = _result()
    result.exception_records[0].values["invalid"] = value
    with pytest.raises((TypeError, ValueError)):
        build_exception_export_table(result)


def test_zero_exception_projection():
    result = replace(_result(), exception_records=(), exception_count=0, exception_rate=0)
    table = build_exception_export_table(result)
    assert table.rows == ()
    assert len(table.headers) == 11
    assert dict(table.metadata)["exception_count"] == 0
