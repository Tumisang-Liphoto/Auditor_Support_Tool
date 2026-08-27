"""Persistence service for audit workspace documents."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from auditor_support_tool.core.constants import APP_VERSION
from auditor_support_tool.core.data_quality_models import (
    DataQualityIssue,
    DataQualityScope,
    DataQualitySeverity,
)
from auditor_support_tool.core.paths import ApplicationPaths
from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
)
from auditor_support_tool.core.source_integrity_service import (
    SourceIntegrityService,
    SourceIntegrityStatus,
)
from auditor_support_tool.core.workbook_package_service import (
    WorkbookPackageRestoreError,
    WorkbookPackageService,
)
from auditor_support_tool.core.workspace_models import (
    WORKSPACE_FILE_EXTENSION,
    WORKSPACE_FORMAT_VERSION,
    TransformationRecord,
    WorkspaceDocument,
    WorkspaceIdentity,
    WorkspaceSourceReference,
)
from auditor_support_tool.core.workspace_state import WorkspaceState


class WorkspaceServiceError(RuntimeError):
    """Raised when a workspace cannot be saved or loaded safely."""


class UnsupportedWorkspaceVersionError(WorkspaceServiceError):
    """Raised when a workspace uses an unsupported format version."""


class WorkspaceSourceIntegrityError(WorkspaceServiceError):
    """Raised when saved source data no longer matches its recorded hash."""

    def __init__(
        self,
        *,
        source_path: Path,
        expected_sha256: str,
        actual_sha256: str,
    ) -> None:
        self.source_path = source_path
        self.expected_sha256 = expected_sha256
        self.actual_sha256 = actual_sha256

        super().__init__(
            "The workspace source file has changed since its integrity hash was recorded."
        )


class WorkspaceService:
    """Save and load persistent audit workspace documents."""

    def __init__(
        self,
        application_paths: ApplicationPaths,
        workbook_package_service: WorkbookPackageService | None = None,
        source_integrity_service: SourceIntegrityService | None = None,
    ) -> None:
        self._application_paths = application_paths
        self._workbook_package_service = workbook_package_service or WorkbookPackageService()
        self._source_integrity_service = source_integrity_service or SourceIntegrityService()

    @property
    def default_workspace_directory(self) -> Path:
        """Return the default directory for saved workspaces."""

        return self._application_paths.workspaces

    def build_document(
        self,
        state: WorkspaceState,
        *,
        source_reference: WorkspaceSourceReference | None = None,
        workbook_package_snapshot: dict[str, object] | None = None,
    ) -> WorkspaceDocument:
        """Build a serialisable document from the active workspace state."""

        identity = state.workspace_identity

        if identity is None:
            raise WorkspaceServiceError("No active audit workspace is available to save.")

        if source_reference is None and state.source_path is not None:
            try:
                source_reference = self._source_reference_for_path(state.source_path)
            except FileNotFoundError:
                source_reference = WorkspaceSourceReference(
                    source_path=str(state.source_path),
                    file_name=state.source_path.name,
                )

        if workbook_package_snapshot is None and state.workbook_package is not None:
            workbook_package_snapshot = self._workbook_package_service.snapshot_package(
                state.workbook_package
            )

        return WorkspaceDocument(
            format_version=WORKSPACE_FORMAT_VERSION,
            application_version=APP_VERSION,
            identity=identity,
            active_dataset_id=state.active_dataset_id,
            source=source_reference,
            workbook_package=workbook_package_snapshot,
            field_mappings={},
            procedure_parameters=state.procedure_parameters,
            procedure_execution_stamps=[
                stamp.to_dict() for stamp in state.procedure_execution_stamps
            ],
            transformation_history=[asdict(record) for record in state.transformation_history],
            data_quality_issues=[asdict(issue) for issue in state.data_quality_issues],
        )

    def save_state(
        self,
        state: WorkspaceState,
        file_path: Path | None = None,
    ) -> Path:
        """Save the active workspace, source file and dataset metadata."""

        target_path = file_path or state.workspace_file_path

        if target_path is None:
            raise WorkspaceServiceError("A workspace file path is required for the first save.")

        workspace_path = self._normalise_workspace_path(target_path)
        workspace_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        source_reference: WorkspaceSourceReference | None = None
        workbook_snapshot: dict[str, object] | None = None

        if state.workbook_package is not None:
            source_reference = self._persist_workspace_source(
                state,
                workspace_path,
            )
            workbook_snapshot = self._workbook_package_service.snapshot_package(
                state.workbook_package
            )
        elif state.source_path is not None:
            source_reference = self._persist_workspace_source(
                state,
                workspace_path,
            )

        document = self.build_document(
            state,
            source_reference=source_reference,
            workbook_package_snapshot=workbook_snapshot,
        )
        saved_path = self.save_document(
            document=document,
            file_path=workspace_path,
        )

        state.set_workspace_file_path(saved_path)
        state.mark_saved()

        return saved_path

    def save_document(
        self,
        document: WorkspaceDocument,
        file_path: Path,
    ) -> Path:
        """Write a workspace document using an atomic replacement."""

        target_path = self._normalise_workspace_path(file_path)
        target_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._validate_document(document)

        temporary_path = target_path.with_suffix(f"{target_path.suffix}.tmp")

        try:
            if target_path.exists():
                self._create_backup(target_path)

            payload = asdict(document)

            serialised_document = json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            )

            temporary_path.write_text(
                serialised_document,
                encoding="utf-8",
            )

            self._verify_written_document(temporary_path)

            temporary_path.replace(target_path)

        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self._remove_file_if_present(temporary_path)

            raise WorkspaceServiceError(f"Could not save workspace: {error}") from error

        return target_path

    def load_document(
        self,
        file_path: Path,
    ) -> WorkspaceDocument:
        """Load and validate a workspace document."""

        workspace_path = self._normalise_workspace_path(file_path)

        if not workspace_path.is_file():
            raise WorkspaceServiceError(f"Workspace file not found: {workspace_path}")

        try:
            raw_document = json.loads(workspace_path.read_text(encoding="utf-8-sig"))
        except OSError as error:
            raise WorkspaceServiceError(f"Could not read workspace file: {error}") from error
        except json.JSONDecodeError as error:
            raise WorkspaceServiceError(
                "The workspace file does not contain valid JSON."
            ) from error

        if not isinstance(raw_document, dict):
            raise WorkspaceServiceError("The workspace file has an invalid top-level structure.")

        document = self._document_from_dict(raw_document)
        self._validate_document(document)

        return document

    def load_into_state(
        self,
        state: WorkspaceState,
        file_path: Path,
        *,
        allow_source_integrity_mismatch: bool = False,
    ) -> WorkspaceDocument:
        """Load a workspace and reconstruct its saved dataset package."""

        workspace_path = self._normalise_workspace_path(file_path)
        document = self.load_document(workspace_path)

        package = None

        if document.workbook_package is not None:
            if document.source is None:
                raise WorkspaceServiceError(
                    "The saved workspace contains dataset metadata but no source-file reference."
                )

            source_path = self._resolve_workspace_source_path(
                document.source,
                workspace_path,
            )

            if not source_path.is_file():
                raise WorkspaceServiceError(
                    f"The workspace-managed source file could not be found: {source_path}"
                )

            try:
                integrity_result = self._source_integrity_service.verify(
                    source_path,
                    document.source.sha256,
                )
            except ValueError as error:
                raise WorkspaceServiceError(
                    f"Could not verify workspace source integrity: {error}"
                ) from error

            if (
                integrity_result.status == SourceIntegrityStatus.MISMATCH
                and not allow_source_integrity_mismatch
            ):
                raise WorkspaceSourceIntegrityError(
                    source_path=source_path,
                    expected_sha256=(integrity_result.expected_sha256 or ""),
                    actual_sha256=(integrity_result.actual_sha256 or ""),
                )

            try:
                package = self._workbook_package_service.restore_package(
                    source_path,
                    document.workbook_package,
                )
            except (
                OSError,
                ValueError,
                WorkbookPackageRestoreError,
            ) as error:
                raise WorkspaceServiceError(f"Could not restore saved datasets: {error}") from error

            if (
                document.active_dataset_id is not None
                and package.get_dataset(document.active_dataset_id) is None
            ):
                raise WorkspaceServiceError(
                    f"The saved active dataset could not be restored: {document.active_dataset_id}"
                )

        transformation_records = [
            self._transformation_record_from_dict(raw_record)
            for raw_record in document.transformation_history
        ]

        data_quality_issues = [
            self._data_quality_issue_from_dict(raw_issue)
            for raw_issue in document.data_quality_issues
        ]

        procedure_execution_stamps = [
            ProcedureExecutionStamp.from_dict(raw_stamp)
            for raw_stamp in document.procedure_execution_stamps
        ]

        state.start_workspace(
            document.identity,
            file_path=workspace_path,
        )

        if package is not None:
            state.set_workbook_package(package)

            if document.active_dataset_id is not None:
                state.set_active_dataset(document.active_dataset_id)

        state.set_transformation_history(
            transformation_records,
            mark_dirty=False,
        )
        state.set_data_quality_issues(
            data_quality_issues,
            mark_dirty=False,
        )
        state.set_all_procedure_parameters(
            document.procedure_parameters,
            mark_dirty=False,
        )
        state.set_all_procedure_execution_stamps(
            procedure_execution_stamps,
            mark_dirty=False,
        )

        state.mark_saved()

        return document

    def _document_from_dict(
        self,
        raw_document: dict[str, Any],
    ) -> WorkspaceDocument:
        """Convert a decoded JSON dictionary to a workspace document."""

        try:
            format_version = int(raw_document["format_version"])
            application_version = str(raw_document["application_version"]).strip()

            raw_identity = raw_document["identity"]

            if not isinstance(raw_identity, dict):
                raise TypeError("Workspace identity must be an object.")

            identity = WorkspaceIdentity(
                workspace_id=str(raw_identity["workspace_id"]),
                name=str(raw_identity["name"]),
                auditee_name=str(
                    raw_identity.get(
                        "auditee_name",
                        "",
                    )
                ),
                audit_year=str(
                    raw_identity.get(
                        "audit_year",
                        "",
                    )
                ),
                audit_period_start=str(
                    raw_identity.get(
                        "audit_period_start",
                        "",
                    )
                ).strip(),
                audit_period_end=str(
                    raw_identity.get(
                        "audit_period_end",
                        "",
                    )
                ).strip(),
                audit_domain=str(
                    raw_identity.get(
                        "audit_domain",
                        "",
                    )
                ),
                audit_area=str(
                    raw_identity.get(
                        "audit_area",
                        "",
                    )
                ),
                lead_auditor=str(
                    raw_identity.get(
                        "lead_auditor",
                        "",
                    )
                ),
                description=str(
                    raw_identity.get(
                        "description",
                        "",
                    )
                ),
                created_at=str(raw_identity["created_at"]),
                modified_at=str(raw_identity["modified_at"]),
            )

            raw_source = raw_document.get("source")
            source: WorkspaceSourceReference | None = None

            if raw_source is not None:
                if not isinstance(raw_source, dict):
                    raise TypeError("Workspace source must be an object.")

                source = WorkspaceSourceReference(
                    source_path=str(raw_source["source_path"]),
                    file_name=str(raw_source["file_name"]),
                    file_size_bytes=self._optional_int(raw_source.get("file_size_bytes")),
                    modified_at=self._optional_string(raw_source.get("modified_at")),
                    sha256=self._optional_string(raw_source.get("sha256")),
                )

            workbook_package = raw_document.get("workbook_package")

            if workbook_package is not None and not isinstance(
                workbook_package,
                dict,
            ):
                raise TypeError("Workbook package must be an object or null.")

            field_mappings = raw_document.get(
                "field_mappings",
                {},
            )

            if not isinstance(field_mappings, dict):
                raise TypeError("Field mappings must be an object.")

            procedure_parameters = self._procedure_parameters_from_raw(
                raw_document.get(
                    "procedure_parameters",
                    {},
                )
            )

            procedure_execution_stamps = self._procedure_execution_stamps_from_raw(
                raw_document.get(
                    "procedure_execution_stamps",
                    [],
                )
            )

            transformation_history = raw_document.get(
                "transformation_history",
                [],
            )

            if not isinstance(
                transformation_history,
                list,
            ):
                raise TypeError("Transformation history must be an array.")

            for history_entry in transformation_history:
                if not isinstance(history_entry, dict):
                    raise TypeError("Transformation history entries must be objects.")

            data_quality_issues = raw_document.get(
                "data_quality_issues",
                [],
            )

            if not isinstance(
                data_quality_issues,
                list,
            ):
                raise TypeError("Data-quality issues must be an array.")

            for data_quality_issue in data_quality_issues:
                if not isinstance(
                    data_quality_issue,
                    dict,
                ):
                    raise TypeError("Data-quality issue entries must be objects.")

            active_dataset_id = self._optional_string(raw_document.get("active_dataset_id"))

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise WorkspaceServiceError(
                f"The workspace file is incomplete or invalid: {error}"
            ) from error

        return WorkspaceDocument(
            format_version=format_version,
            application_version=application_version,
            identity=identity,
            active_dataset_id=active_dataset_id,
            source=source,
            workbook_package=workbook_package,
            field_mappings=field_mappings,
            procedure_parameters=procedure_parameters,
            procedure_execution_stamps=procedure_execution_stamps,
            transformation_history=transformation_history,
            data_quality_issues=data_quality_issues,
        )

    @staticmethod
    def _procedure_execution_stamps_from_raw(
        raw_stamps: object,
    ) -> list[dict[str, object]]:
        """Validate saved successful procedure execution stamps."""

        if not isinstance(raw_stamps, list):
            raise TypeError("Procedure execution stamps must be an array.")

        cleaned: list[dict[str, object]] = []

        for raw_stamp in raw_stamps:
            if not isinstance(raw_stamp, dict):
                raise TypeError("Procedure execution stamp entries must be objects.")

            try:
                stamp = ProcedureExecutionStamp.from_dict(raw_stamp)
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                raise TypeError(f"Invalid procedure execution stamp: {error}") from error

            cleaned.append(stamp.to_dict())

        return cleaned

    @staticmethod
    def _procedure_parameters_from_raw(
        raw_parameters: object,
    ) -> dict[str, dict[str, object]]:
        """Validate and copy saved procedure parameter values."""

        if not isinstance(raw_parameters, dict):
            raise TypeError("Procedure parameters must be an object.")

        cleaned: dict[str, dict[str, object]] = {}

        for raw_procedure_id, raw_values in raw_parameters.items():
            procedure_id = str(raw_procedure_id).strip()

            if not procedure_id:
                raise TypeError("Procedure parameter procedure IDs cannot be blank.")

            if not isinstance(
                raw_values,
                dict,
            ):
                raise TypeError("Each procedure parameter entry must be an object.")

            cleaned_values: dict[str, object] = {}

            for raw_key, value in raw_values.items():
                key = str(raw_key).strip()

                if not key:
                    raise TypeError("Procedure parameter keys cannot be blank.")

                cleaned_values[key] = value

            if cleaned_values:
                cleaned[procedure_id] = cleaned_values

        try:
            json.dumps(cleaned)
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TypeError("Procedure parameter values must be JSON-compatible.") from error

        return cleaned

    @staticmethod
    def _data_quality_issue_from_dict(
        raw_issue: dict[str, object],
    ) -> DataQualityIssue:
        """Convert one saved data-quality entry to its model."""

        if not isinstance(raw_issue, dict):
            raise WorkspaceServiceError("Data-quality issue entries must be objects.")

        try:
            issue_id = str(raw_issue["issue_id"]).strip()
            detected_at = str(raw_issue["detected_at"]).strip()
            code = str(raw_issue["code"]).strip()
            message = str(raw_issue["message"]).strip()
            dataset_id = str(raw_issue["dataset_id"]).strip()

            if not issue_id:
                raise ValueError("Data-quality issue identifier is required.")

            if not detected_at:
                raise ValueError("Data-quality detection time is required.")

            if not code:
                raise ValueError("Data-quality issue code is required.")

            if not message:
                raise ValueError("Data-quality issue message is required.")

            if not dataset_id:
                raise ValueError("Data-quality dataset identifier is required.")

            severity = DataQualitySeverity(str(raw_issue["severity"]))
            scope = DataQualityScope(str(raw_issue["scope"]))

            details = raw_issue.get(
                "details",
                {},
            )

            if not isinstance(details, dict):
                raise TypeError("Data-quality details must be an object.")

            affected_record_count = WorkspaceService._optional_int(
                raw_issue.get("affected_record_count")
            )

            return DataQualityIssue(
                issue_id=issue_id,
                detected_at=detected_at,
                code=code,
                severity=severity,
                scope=scope,
                message=message,
                dataset_id=dataset_id,
                column_id=WorkspaceService._optional_string(raw_issue.get("column_id")),
                source_column=WorkspaceService._optional_string(raw_issue.get("source_column")),
                standard_field_key=(
                    WorkspaceService._optional_string(raw_issue.get("standard_field_key"))
                ),
                affected_record_count=affected_record_count,
                details=dict(details),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise WorkspaceServiceError(f"Invalid data-quality issue entry: {error}") from error

    @staticmethod
    def _transformation_record_from_dict(
        raw_record: dict[str, object],
    ) -> TransformationRecord:
        """Convert one saved transformation-history entry to its model."""

        if not isinstance(raw_record, dict):
            raise WorkspaceServiceError("Transformation history entries must be objects.")

        try:
            record_id = str(raw_record["record_id"]).strip()
            timestamp = str(raw_record["timestamp"]).strip()
            action = str(raw_record["action"]).strip()

            if not record_id:
                raise ValueError("Transformation record identifier is required.")

            if not timestamp:
                raise ValueError("Transformation timestamp is required.")

            if not action:
                raise ValueError("Transformation action is required.")

            details = raw_record.get(
                "details",
                {},
            )

            if not isinstance(details, dict):
                raise TypeError("Transformation details must be an object.")

            return TransformationRecord(
                record_id=record_id,
                timestamp=timestamp,
                action=action,
                dataset_id=(WorkspaceService._optional_string(raw_record.get("dataset_id"))),
                column_id=(WorkspaceService._optional_string(raw_record.get("column_id"))),
                source_column=(WorkspaceService._optional_string(raw_record.get("source_column"))),
                old_value=raw_record.get("old_value"),
                new_value=raw_record.get("new_value"),
                details=dict(details),
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise WorkspaceServiceError(f"Invalid transformation-history entry: {error}") from error

    def _validate_document(
        self,
        document: WorkspaceDocument,
    ) -> None:
        """Validate the workspace document before use."""

        if document.format_version != WORKSPACE_FORMAT_VERSION:
            raise UnsupportedWorkspaceVersionError(
                "Unsupported workspace format version: "
                f"{document.format_version}. "
                f"Supported version: "
                f"{WORKSPACE_FORMAT_VERSION}."
            )

        if not document.application_version.strip():
            raise WorkspaceServiceError("Workspace application version is required.")

        if not document.identity.workspace_id.strip():
            raise WorkspaceServiceError("Workspace identifier is required.")

        if not document.identity.name.strip():
            raise WorkspaceServiceError("Workspace name is required.")

        try:
            document.identity.validate_audit_period()
        except ValueError as error:
            raise WorkspaceServiceError(f"Invalid audit period: {error}") from error

        try:
            self._procedure_parameters_from_raw(document.procedure_parameters)
        except TypeError as error:
            raise WorkspaceServiceError(f"Invalid procedure parameters: {error}") from error

        try:
            self._procedure_execution_stamps_from_raw(document.procedure_execution_stamps)
        except TypeError as error:
            raise WorkspaceServiceError(f"Invalid procedure execution stamps: {error}") from error

        if not document.identity.created_at.strip():
            raise WorkspaceServiceError("Workspace creation date is required.")

        if not document.identity.modified_at.strip():
            raise WorkspaceServiceError("Workspace modification date is required.")

    def _verify_written_document(
        self,
        temporary_path: Path,
    ) -> None:
        """Verify that the temporary file can be decoded."""

        raw_document = json.loads(temporary_path.read_text(encoding="utf-8"))

        if not isinstance(raw_document, dict):
            raise WorkspaceServiceError("The temporary workspace file is invalid.")

        document = self._document_from_dict(raw_document)
        self._validate_document(document)

    def _source_reference_for_path(
        self,
        file_path: Path,
    ) -> WorkspaceSourceReference:
        """Create a source reference including a SHA-256 integrity hash."""

        resolved_path = file_path.expanduser().resolve()
        source_hash = self._source_integrity_service.sha256_file(resolved_path)

        return WorkspaceSourceReference.from_path(
            resolved_path,
            sha256=source_hash,
        )

    def _persist_workspace_source(
        self,
        state: WorkspaceState,
        workspace_path: Path,
    ) -> WorkspaceSourceReference:
        """Copy the active source into the workspace companion folder."""

        source_path = state.source_path

        if source_path is None:
            raise WorkspaceServiceError("The active workspace does not have a source file.")

        source_path = source_path.expanduser().resolve()

        if not source_path.is_file():
            existing_managed_path = self._managed_source_path(
                workspace_path,
                source_path.name,
            )

            if existing_managed_path.is_file():
                source_path = existing_managed_path
            else:
                raise WorkspaceServiceError(
                    f"The workspace source file is no longer available: {source_path}"
                )

        managed_path = self._managed_source_path(
            workspace_path,
            source_path.name,
        )

        try:
            managed_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if source_path != managed_path:
                self._copy_source_if_needed(
                    source_path,
                    managed_path,
                )

            absolute_reference = self._source_reference_for_path(managed_path)

        except OSError as error:
            raise WorkspaceServiceError(
                f"Could not preserve workspace source data: {error}"
            ) from error

        try:
            relative_source = managed_path.relative_to(workspace_path.parent)
        except ValueError:
            relative_source = managed_path

        return WorkspaceSourceReference(
            source_path=str(relative_source),
            file_name=absolute_reference.file_name,
            file_size_bytes=(absolute_reference.file_size_bytes),
            modified_at=absolute_reference.modified_at,
            sha256=absolute_reference.sha256,
        )

    @staticmethod
    def _managed_source_path(
        workspace_path: Path,
        source_file_name: str,
    ) -> Path:
        """Return the companion source path for a saved workspace."""

        data_directory = workspace_path.parent / f"{workspace_path.stem}.astdata"

        return (data_directory / "source" / source_file_name).resolve()

    @staticmethod
    def _copy_source_if_needed(
        source_path: Path,
        destination_path: Path,
    ) -> None:
        """Copy source data atomically when the managed copy is outdated."""

        if destination_path.is_file():
            source_stat = source_path.stat()
            destination_stat = destination_path.stat()

            if (
                source_stat.st_size == destination_stat.st_size
                and source_stat.st_mtime_ns == destination_stat.st_mtime_ns
            ):
                return

        temporary_path = destination_path.with_suffix(f"{destination_path.suffix}.tmp")

        try:
            shutil.copy2(
                source_path,
                temporary_path,
            )

            if temporary_path.stat().st_size != source_path.stat().st_size:
                raise OSError("Workspace source copy size does not match the original.")

            temporary_path.replace(destination_path)

        except OSError:
            temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _resolve_workspace_source_path(
        source_reference: WorkspaceSourceReference,
        workspace_path: Path,
    ) -> Path:
        """Resolve an absolute or workspace-relative saved source path."""

        candidate = Path(source_reference.source_path).expanduser()

        if candidate.is_absolute():
            return candidate.resolve()

        return (workspace_path.parent / candidate).resolve()

    def _create_backup(
        self,
        source_path: Path,
    ) -> Path:
        """Copy the current workspace file to the backup directory."""

        backup_directory = self._application_paths.workspace_backups / source_path.stem
        backup_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"{source_path.stem}-{timestamp}{WORKSPACE_FILE_EXTENSION}"
        backup_path = backup_directory / backup_name

        shutil.copy2(
            source_path,
            backup_path,
        )

        return backup_path

    @staticmethod
    def _normalise_workspace_path(
        file_path: Path,
    ) -> Path:
        """Return a resolved path with the workspace extension."""

        candidate = file_path.expanduser()

        if candidate.suffix.lower() != WORKSPACE_FILE_EXTENSION:
            candidate = candidate.with_suffix(WORKSPACE_FILE_EXTENSION)

        return candidate.resolve()

    @staticmethod
    def _remove_file_if_present(
        file_path: Path,
    ) -> None:
        """Remove a temporary file where it exists."""

        try:
            file_path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _optional_string(
        value: object,
    ) -> str | None:
        """Convert an optional value to text."""

        if value is None:
            return None

        return str(value)

    @staticmethod
    def _optional_int(
        value: object,
    ) -> int | None:
        """Convert an optional value to an integer."""

        if value is None:
            return None

        return int(value)
