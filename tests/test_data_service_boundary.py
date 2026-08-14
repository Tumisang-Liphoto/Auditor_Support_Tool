"""Tests for the generic data-service compatibility boundary."""

from auditor_support_tool.core.data_import_service import (
    CSV_WORKSHEET_NAME as CoreCSVWorksheetName,
)
from auditor_support_tool.core.data_import_service import (
    DataImportError as CoreDataImportError,
)
from auditor_support_tool.core.data_import_service import (
    DataImportService as CoreDataImportService,
)
from auditor_support_tool.core.data_profile_service import (
    DataProfileService as CoreDataProfileService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_import_service import (
    CSV_WORKSHEET_NAME as GeneralLedgerCSVWorksheetName,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_import_service import (
    DataImportError as GeneralLedgerDataImportError,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_import_service import (
    DataImportService as GeneralLedgerDataImportService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_service import (
    DataProfileService as GeneralLedgerDataProfileService,
)


def test_general_ledger_import_service_reexports_core_service() -> None:
    """Legacy GL imports should resolve to the generic core import service."""

    assert GeneralLedgerDataImportService is CoreDataImportService
    assert GeneralLedgerDataImportError is CoreDataImportError
    assert GeneralLedgerCSVWorksheetName == CoreCSVWorksheetName


def test_general_ledger_profile_service_reexports_core_service() -> None:
    """Legacy GL imports should resolve to the generic core profile service."""

    assert GeneralLedgerDataProfileService is CoreDataProfileService
