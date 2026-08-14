"""Compatibility exports for shared source-data profiling models.

General Ledger profiling code may continue importing from this module while
the generic model definitions live in ``auditor_support_tool.core``.
"""

from auditor_support_tool.core.data_profile_models import (
    ColumnProfile,
    DataProfile,
    DetectedDataType,
)

__all__ = [
    "ColumnProfile",
    "DataProfile",
    "DetectedDataType",
]
