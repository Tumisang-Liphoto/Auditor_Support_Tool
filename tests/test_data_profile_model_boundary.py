"""Tests for the generic data-profile model boundary."""

from auditor_support_tool.core.data_profile_models import (
    ColumnProfile as CoreColumnProfile,
)
from auditor_support_tool.core.data_profile_models import (
    DataProfile as CoreDataProfile,
)
from auditor_support_tool.core.data_profile_models import (
    DetectedDataType as CoreDetectedDataType,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    ColumnProfile as GeneralLedgerColumnProfile,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DataProfile as GeneralLedgerDataProfile,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_models import (
    DetectedDataType as GeneralLedgerDetectedDataType,
)


def test_general_ledger_profile_models_reexport_core_types() -> None:
    """Compatibility imports should resolve to the generic core types."""

    assert GeneralLedgerColumnProfile is CoreColumnProfile
    assert GeneralLedgerDataProfile is CoreDataProfile
    assert GeneralLedgerDetectedDataType is CoreDetectedDataType


def test_detected_data_type_values_are_preserved() -> None:
    """Moving the enum must not change persisted type values."""

    assert CoreDetectedDataType.BLANK.value == "blank"
    assert CoreDetectedDataType.TEXT.value == "text"
    assert CoreDetectedDataType.INTEGER.value == "integer"
    assert CoreDetectedDataType.DECIMAL.value == "decimal"
    assert CoreDetectedDataType.DATE.value == "date"
    assert CoreDetectedDataType.DATETIME.value == "datetime"
    assert CoreDetectedDataType.BOOLEAN.value == "boolean"
    assert CoreDetectedDataType.MIXED.value == "mixed"
