"""Tests for the generic source-data model boundary."""

from auditor_support_tool.core.data_models import (
    SOURCE_ROW_FIELD as CORE_SOURCE_ROW_FIELD,
)
from auditor_support_tool.core.data_models import (
    LoadedTable as CoreLoadedTable,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    SOURCE_ROW_FIELD as GL_SOURCE_ROW_FIELD,
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable as GeneralLedgerLoadedTable,
)


def test_general_ledger_models_reexport_core_loaded_table() -> None:
    """Domain compatibility imports should resolve to the core model."""

    assert GeneralLedgerLoadedTable is CoreLoadedTable


def test_source_row_field_is_defined_once_in_core() -> None:
    """Stable source-row identity should be a platform-level convention."""

    assert CORE_SOURCE_ROW_FIELD == "_source_row_number"
    assert GL_SOURCE_ROW_FIELD == CORE_SOURCE_ROW_FIELD
