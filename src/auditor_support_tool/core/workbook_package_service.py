"""Build a multi-worksheet workbook package from a source file."""

from pathlib import Path

from auditor_support_tool.core.workbook_package import (
    PreparationStatus,
    PreparedColumn,
    WorkbookPackage,
    WorksheetDataset,
)
from auditor_support_tool.core.workbook_suggestion_service import (
    WorkbookSuggestionService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_import_service import (
    DataImportService,
)
from auditor_support_tool.domains.financial_audit.general_ledger.data_profile_service import (
    DataProfileService,
)


class WorkbookPackageService:
    """Inspect, load, profile and suggest workbook datasets."""

    def __init__(
        self,
        import_service: DataImportService | None = None,
        profile_service: DataProfileService | None = None,
        suggestion_service: WorkbookSuggestionService | None = None,
    ) -> None:
        self._import_service = import_service or DataImportService()
        self._profile_service = profile_service or DataProfileService()
        self._suggestion_service = suggestion_service or WorkbookSuggestionService()

    def build_package(
        self,
        source_path: str | Path,
        *,
        include_empty_worksheets: bool = False,
    ) -> WorkbookPackage:
        """Build a package containing every relevant worksheet."""

        source_info = self._import_service.inspect_source(source_path)

        package = WorkbookPackage(
            source_path=source_info.path,
            source_info=source_info,
        )

        for worksheet_number, worksheet_info in enumerate(
            source_info.worksheets,
            start=1,
        ):
            if not include_empty_worksheets and worksheet_info.estimated_data_rows == 0:
                continue

            table = self._import_service.load_table(
                source_info.path,
                worksheet_name=worksheet_info.name,
            )

            profile = self._profile_service.profile(table)

            (
                suggested_name,
                suggested_type,
                confidence,
            ) = self._suggestion_service.suggest_dataset(
                worksheet_info.name,
                table.headers,
            )

            columns = [self._prepare_column(column_profile) for column_profile in profile.columns]

            package.datasets.append(
                WorksheetDataset(
                    dataset_id=(f"dataset-{worksheet_number:04d}"),
                    original_worksheet_name=worksheet_info.name,
                    suggested_display_name=suggested_name,
                    confirmed_display_name=suggested_name,
                    suggested_dataset_type=suggested_type,
                    confirmed_dataset_type=suggested_type,
                    suggestion_confidence=confidence,
                    status=PreparationStatus.NOT_REVIEWED,
                    selected=True,
                    loaded_table=table,
                    data_profile=profile,
                    columns=columns,
                )
            )

        return package

    def _prepare_column(
        self,
        column_profile,
    ) -> PreparedColumn:
        (
            suggested_name,
            confidence,
        ) = self._suggestion_service.suggest_column_name(column_profile)

        return PreparedColumn(
            source_column=column_profile.column_name,
            position=column_profile.position,
            detected_type=column_profile.detected_type,
            suggested_name=suggested_name,
            confirmed_name=suggested_name,
            suggested_type=column_profile.detected_type,
            confirmed_type=column_profile.detected_type,
            suggestion_confidence=confidence,
            status=PreparationStatus.NOT_REVIEWED,
        )
