"""Compatibility exports for shared source-data models.

General Ledger import/profile code may continue importing from this module,
but the actual model definitions live in ``auditor_support_tool.core`` so the
core platform no longer depends on the General Ledger domain for these types.
"""

from auditor_support_tool.core.data_models import (
    SOURCE_ROW_FIELD,
    HeaderChange,
    LoadedTable,
    PopulationSummary,
    SourceFileInfo,
    WorksheetInfo,
)

__all__ = [
    "SOURCE_ROW_FIELD",
    "HeaderChange",
    "LoadedTable",
    "PopulationSummary",
    "SourceFileInfo",
    "WorksheetInfo",
]
