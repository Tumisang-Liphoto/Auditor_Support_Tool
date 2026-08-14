"""Compatibility export for the generic audit data profiling service.

General Ledger code may continue importing from this module while the
implementation lives in ``auditor_support_tool.core``.
"""

from auditor_support_tool.core.data_profile_service import DataProfileService

__all__ = [
    "DataProfileService",
]
