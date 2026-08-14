"""Persistent audit workspace models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

WORKSPACE_FILE_EXTENSION = ".astworkspace"
WORKSPACE_FORMAT_VERSION = 1


def utc_now_iso() -> str:
    """Return the current UTC date and time in ISO 8601 format."""

    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class TransformationRecord:
    """One auditable change made to workspace data or preparation state."""

    record_id: str
    timestamp: str
    action: str

    dataset_id: str | None = None
    column_id: str | None = None
    source_column: str | None = None

    old_value: object | None = None
    new_value: object | None = None
    details: dict[str, object] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        action: str,
        dataset_id: str | None = None,
        column_id: str | None = None,
        source_column: str | None = None,
        old_value: object | None = None,
        new_value: object | None = None,
        details: dict[str, object] | None = None,
    ) -> TransformationRecord:
        """Create a transformation record with a stable ID and UTC timestamp."""

        cleaned_action = action.strip()

        if not cleaned_action:
            raise ValueError("Transformation action is required.")

        return cls(
            record_id=str(uuid4()),
            timestamp=utc_now_iso(),
            action=cleaned_action,
            dataset_id=dataset_id.strip() if dataset_id else None,
            column_id=column_id.strip() if column_id else None,
            source_column=source_column.strip() if source_column else None,
            old_value=old_value,
            new_value=new_value,
            details=dict(details or {}),
        )


@dataclass(slots=True)
class WorkspaceIdentity:
    """Identity and descriptive metadata for one audit workspace."""

    workspace_id: str
    name: str
    auditee_name: str = ""
    audit_year: str = ""
    audit_domain: str = ""
    audit_area: str = ""
    lead_auditor: str = ""
    description: str = ""

    created_at: str = field(default_factory=utc_now_iso)
    modified_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        auditee_name: str = "",
        audit_year: str = "",
        audit_domain: str = "",
        audit_area: str = "",
        lead_auditor: str = "",
        description: str = "",
    ) -> WorkspaceIdentity:
        """Create a new workspace identity."""

        cleaned_name = name.strip()

        if not cleaned_name:
            raise ValueError("Workspace name is required.")

        return cls(
            workspace_id=str(uuid4()),
            name=cleaned_name,
            auditee_name=auditee_name.strip(),
            audit_year=audit_year.strip(),
            audit_domain=audit_domain.strip(),
            audit_area=audit_area.strip(),
            lead_auditor=lead_auditor.strip(),
            description=description.strip(),
        )

    def touch(self) -> None:
        """Update the last-modified timestamp."""

        self.modified_at = utc_now_iso()


@dataclass(slots=True)
class WorkspaceSourceReference:
    """Reference to a source file used by the workspace."""

    source_path: str
    file_name: str
    file_size_bytes: int | None = None
    modified_at: str | None = None
    sha256: str | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        *,
        sha256: str | None = None,
    ) -> WorkspaceSourceReference:
        """Create a source reference from an existing file path."""

        resolved_path = path.expanduser().resolve()

        if not resolved_path.is_file():
            raise FileNotFoundError(f"Source file not found: {resolved_path}")

        file_status = resolved_path.stat()

        return cls(
            source_path=str(resolved_path),
            file_name=resolved_path.name,
            file_size_bytes=file_status.st_size,
            modified_at=datetime.fromtimestamp(
                file_status.st_mtime,
                tz=UTC,
            ).isoformat(),
            sha256=sha256.strip().lower() if sha256 else None,
        )

    @property
    def path(self) -> Path:
        """Return the source reference as a Path."""

        return Path(self.source_path)

    @property
    def exists(self) -> bool:
        """Return whether the referenced source file still exists."""

        return self.path.is_file()


@dataclass(slots=True)
class WorkspaceDocument:
    """Serializable document representing one audit workspace."""

    format_version: int
    application_version: str
    identity: WorkspaceIdentity

    active_dataset_id: str | None = None
    source: WorkspaceSourceReference | None = None

    workbook_package: dict[str, object] | None = None
    field_mappings: dict[str, object] = field(default_factory=dict)
    transformation_history: list[dict[str, object]] = field(default_factory=list)
    data_quality_issues: list[dict[str, object]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        identity: WorkspaceIdentity,
        application_version: str,
    ) -> WorkspaceDocument:
        """Create an empty persistent workspace document."""

        return cls(
            format_version=WORKSPACE_FORMAT_VERSION,
            application_version=application_version,
            identity=identity,
        )
