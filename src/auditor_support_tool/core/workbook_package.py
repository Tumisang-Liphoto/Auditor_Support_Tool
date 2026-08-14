"""Models for a workbook containing multiple prepared audit datasets."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from auditor_support_tool.core.data_models import (
    LoadedTable,
    SourceFileInfo,
)
from auditor_support_tool.core.data_profile_models import (
    DataProfile,
    DetectedDataType,
)


def new_column_id() -> str:
    """Return a new stable identifier for a prepared source column."""

    return f"column-{uuid4().hex}"


class DatasetType(StrEnum):
    """Recognised types of audit datasets."""

    GENERAL_LEDGER = "general_ledger"
    CHART_OF_ACCOUNTS = "chart_of_accounts"
    TRIAL_BALANCE = "trial_balance"
    VENDOR_MASTER = "vendor_master"
    CUSTOMER_MASTER = "customer_master"
    BANK_TRANSACTIONS = "bank_transactions"
    PAYROLL_REGISTER = "payroll_register"
    EMPLOYEE_MASTER = "employee_master"
    FIXED_ASSET_REGISTER = "fixed_asset_register"
    JOURNAL_LISTING = "journal_listing"
    USER_ACCESS_LISTING = "user_access_listing"
    OTHER = "other"
    UNCLASSIFIED = "unclassified"


class MappingConfidence(StrEnum):
    """Confidence attached to an application-generated suggestion."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class PreparationStatus(StrEnum):
    """Preparation status for a worksheet or column."""

    NOT_REVIEWED = "not_reviewed"
    CONFIRMED = "confirmed"
    CONFIRMED_WITH_WARNINGS = "confirmed_with_warnings"
    REVIEW_REQUIRED = "review_required"
    EXCLUDED = "excluded"


class FieldMappingStatus(StrEnum):
    """Field-mapping status for a prepared dataset."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    CONFIRMED = "confirmed"
    CONFIRMED_WITH_WARNINGS = "confirmed_with_warnings"
    REVIEW_REQUIRED = "review_required"
    NOT_APPLICABLE = "not_applicable"


@dataclass(slots=True)
class PreparedColumn:
    """Preparation information for one source column."""

    source_column: str
    position: int
    detected_type: DetectedDataType

    suggested_name: str
    confirmed_name: str

    suggested_type: DetectedDataType
    confirmed_type: DetectedDataType

    suggestion_confidence: MappingConfidence = MappingConfidence.NONE
    status: PreparationStatus = PreparationStatus.NOT_REVIEWED

    included: bool = True
    validation_warning: str = ""

    column_id: str = field(default_factory=new_column_id)

    @property
    def name_was_changed(self) -> bool:
        """Return whether the prepared name differs from its suggestion."""

        return self.confirmed_name.strip() != self.suggested_name.strip()

    @property
    def type_was_changed(self) -> bool:
        """Return whether the confirmed type differs from its suggestion."""

        return self.confirmed_type != self.suggested_type

    @property
    def was_changed(self) -> bool:
        """Return whether the prepared name or type was changed."""

        return self.name_was_changed or self.type_was_changed


@dataclass(slots=True)
class WorksheetDataset:
    """One worksheet loaded as a separate dataset."""

    dataset_id: str
    original_worksheet_name: str

    suggested_display_name: str
    confirmed_display_name: str

    suggested_dataset_type: DatasetType
    confirmed_dataset_type: DatasetType

    suggestion_confidence: MappingConfidence
    status: PreparationStatus

    selected: bool
    loaded_table: LoadedTable
    data_profile: DataProfile

    preparation_status: PreparationStatus = PreparationStatus.NOT_REVIEWED
    mapping_status: FieldMappingStatus = FieldMappingStatus.NOT_STARTED

    field_mappings: dict[str, str] = field(default_factory=dict)
    columns: list[PreparedColumn] = field(default_factory=list)

    @property
    def record_count(self) -> int:
        """Return the number of loaded records."""

        return self.loaded_table.record_count

    @property
    def column_count(self) -> int:
        """Return the number of loaded source columns."""

        return self.loaded_table.column_count

    @property
    def included_columns(self) -> tuple[PreparedColumn, ...]:
        """Return columns included in the prepared dataset."""

        return tuple(column for column in self.columns if column.included)

    @property
    def included_source_columns(self) -> tuple[str, ...]:
        """Return source-column names included in preparation."""

        return tuple(column.source_column for column in self.columns if column.included)

    @property
    def mapped_standard_fields(self) -> tuple[str, ...]:
        """Return standard-field keys already mapped."""

        return tuple(self.field_mappings.values())

    def get_column(
        self,
        column_id: str,
    ) -> PreparedColumn | None:
        """Return a prepared column by its stable identifier."""

        for column in self.columns:
            if column.column_id == column_id:
                return column

        return None


@dataclass(slots=True)
class WorkbookPackage:
    """An uploaded workbook and all selected worksheet datasets."""

    source_path: Path
    source_info: SourceFileInfo
    datasets: list[WorksheetDataset] = field(default_factory=list)

    @property
    def source_file_name(self) -> str:
        """Return the original workbook filename."""

        return self.source_path.name

    @property
    def selected_datasets(self) -> tuple[WorksheetDataset, ...]:
        """Return datasets selected for preparation and mapping."""

        return tuple(dataset for dataset in self.datasets if dataset.selected)

    def get_dataset(
        self,
        dataset_id: str,
    ) -> WorksheetDataset | None:
        """Return a dataset by its stable identifier."""

        for dataset in self.datasets:
            if dataset.dataset_id == dataset_id:
                return dataset

        return None

    def get_dataset_by_worksheet(
        self,
        worksheet_name: str,
    ) -> WorksheetDataset | None:
        """Return a dataset by its original worksheet name."""

        for dataset in self.datasets:
            if dataset.original_worksheet_name == worksheet_name:
                return dataset

        return None
