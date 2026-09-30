"""Local autosave recovery for the authoritative workspace document format."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from auditor_support_tool.core.paths import ApplicationPaths
from auditor_support_tool.core.workspace_models import WorkspaceDocument
from auditor_support_tool.core.workspace_service import WorkspaceService, WorkspaceServiceError
from auditor_support_tool.core.workspace_state import WorkspaceState

RECOVERY_FILE_NAME = "active-workspace-recovery.astworkspace"


class WorkspaceRecoveryError(RuntimeError):
    """Raised when a recovery snapshot cannot be saved, inspected, or restored."""


@dataclass(frozen=True, slots=True)
class WorkspaceRecoverySnapshot:
    """One validated recovery snapshot available for startup restoration."""

    path: Path
    modified_at: datetime
    document: WorkspaceDocument


class WorkspaceRecoveryService:
    """Persist one atomic recovery snapshot without changing official Save state."""

    def __init__(
        self,
        application_paths: ApplicationPaths,
        workspace_service: WorkspaceService,
    ) -> None:
        self._workspace_service = workspace_service
        self._recovery_path = application_paths.workspace_recovery / RECOVERY_FILE_NAME

    @property
    def recovery_path(self) -> Path:
        """Return the per-user recovery snapshot path."""

        return self._recovery_path

    def save(self, state: WorkspaceState) -> WorkspaceRecoverySnapshot:
        """Atomically replace the recovery snapshot with current workspace configuration."""

        try:
            source_reference = self._workspace_service.loaded_source_reference(state)
            document = self._workspace_service.build_document(
                state,
                source_reference=source_reference,
            )
            path = self._workspace_service.save_document(
                document,
                self._recovery_path,
                create_backup=False,
            )
            return WorkspaceRecoverySnapshot(
                path=path,
                modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                document=document,
            )
        except (OSError, TypeError, ValueError, WorkspaceServiceError) as error:
            raise WorkspaceRecoveryError(f"Could not autosave workspace: {error}") from error

    def discover(self) -> WorkspaceRecoverySnapshot | None:
        """Return the validated recovery snapshot, if one exists."""

        if not self._recovery_path.is_file():
            return None

        try:
            document = self._workspace_service.load_document(self._recovery_path)
            modified_at = datetime.fromtimestamp(
                self._recovery_path.stat().st_mtime,
                tz=UTC,
            )
        except (OSError, TypeError, ValueError, WorkspaceServiceError) as error:
            raise WorkspaceRecoveryError(
                "The autosaved workspace is corrupt or cannot be validated."
            ) from error

        return WorkspaceRecoverySnapshot(
            path=self._recovery_path,
            modified_at=modified_at,
            document=document,
        )

    def restore(self, state: WorkspaceState) -> WorkspaceDocument:
        """Load recovery configuration and leave it explicitly unsaved."""

        snapshot = self.discover()
        if snapshot is None:
            raise WorkspaceRecoveryError("No autosaved workspace is available.")

        try:
            document = self._workspace_service.load_into_state(state, snapshot.path)
        except (OSError, TypeError, ValueError, WorkspaceServiceError) as error:
            raise WorkspaceRecoveryError(
                f"Could not restore autosaved workspace: {error}"
            ) from error

        state.set_workspace_file_path(None)
        state.mark_dirty()
        return document

    def discard(self) -> None:
        """Remove the active recovery snapshot and any incomplete temporary write."""

        temporary_path = self._recovery_path.with_suffix(f"{self._recovery_path.suffix}.tmp")
        try:
            self._recovery_path.unlink(missing_ok=True)
            temporary_path.unlink(missing_ok=True)
        except OSError as error:
            raise WorkspaceRecoveryError(
                f"Could not remove autosaved workspace: {error}"
            ) from error
