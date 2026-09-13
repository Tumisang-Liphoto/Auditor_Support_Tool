"""Tests for dataset-aware procedure execution state."""

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureRunContext,
)
from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
)
from auditor_support_tool.core.workspace_models import (
    WorkspaceIdentity,
)
from auditor_support_tool.core.workspace_state import (
    WorkspaceState,
)


def create_stamp(
    *,
    procedure_id: str,
    dataset_id: str,
) -> ProcedureExecutionStamp:
    """Create one successful execution stamp."""

    request = AuditExecutionRequest.create(
        procedure_id=procedure_id,
        dataset_id=dataset_id,
    )

    context = ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
    )

    return ProcedureExecutionStamp.from_context(context)


def test_execution_stamps_are_dataset_specific() -> None:
    """Running a procedure on one dataset must not overwrite another."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit"))

    dataset_one = create_stamp(
        procedure_id="GL001",
        dataset_id="dataset-1",
    )
    dataset_two = create_stamp(
        procedure_id="GL001",
        dataset_id="dataset-2",
    )

    state.record_procedure_execution(dataset_one)
    state.record_procedure_execution(dataset_two)

    assert (
        state.get_procedure_execution_stamp(
            "GL001",
            "dataset-1",
        )
        == dataset_one
    )
    assert (
        state.get_procedure_execution_stamp(
            "GL-001",
            "dataset-2",
        )
        == dataset_two
    )


def test_recording_successful_execution_marks_workspace_dirty() -> None:
    """Execution status must be persisted with the workspace."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit"))
    state.mark_saved()

    state.record_procedure_execution(
        create_stamp(
            procedure_id="GL003",
            dataset_id="dataset-1",
        )
    )

    assert state.is_dirty is True


def test_restoring_execution_stamps_can_keep_workspace_clean() -> None:
    """Workspace loading should not create artificial unsaved changes."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit"))

    stamp = create_stamp(
        procedure_id="GL003",
        dataset_id="dataset-1",
    )

    state.set_all_procedure_execution_stamps(
        [stamp],
        mark_dirty=False,
    )
    state.mark_saved()

    assert (
        state.get_procedure_execution_stamp(
            "GL003",
            "dataset-1",
        )
        == stamp
    )
    assert state.is_dirty is False


def test_failed_rerun_requirement_preserves_successful_stamp() -> None:
    """A newer failed attempt must not destroy successful execution evidence."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit"))

    stamp = create_stamp(
        procedure_id="GL001",
        dataset_id="dataset-1",
    )

    state.record_procedure_execution(stamp)
    state.mark_saved()

    state.mark_procedure_rerun_required(
        "GL001",
        "dataset-1",
    )

    assert (
        state.get_procedure_execution_stamp(
            "GL001",
            "dataset-1",
        )
        == stamp
    )
    assert state.procedure_requires_rerun(
        "GL001",
        "dataset-1",
    )
    assert state.is_dirty is True


def test_first_failed_attempt_does_not_create_rerun_requirement() -> None:
    """Needs Re-run only qualifies an earlier successful execution."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit"))

    state.mark_procedure_rerun_required(
        "GL001",
        "dataset-1",
    )

    assert not state.procedure_requires_rerun(
        "GL001",
        "dataset-1",
    )


def test_successful_rerun_clears_rerun_requirement() -> None:
    """A later successful execution becomes authoritative again."""

    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Audit"))

    first_stamp = create_stamp(
        procedure_id="GL001",
        dataset_id="dataset-1",
    )
    state.record_procedure_execution(first_stamp)
    state.mark_procedure_rerun_required(
        "GL001",
        "dataset-1",
    )

    assert state.procedure_requires_rerun(
        "GL001",
        "dataset-1",
    )

    second_stamp = create_stamp(
        procedure_id="GL001",
        dataset_id="dataset-1",
    )
    state.record_procedure_execution(second_stamp)

    assert (
        state.get_procedure_execution_stamp(
            "GL001",
            "dataset-1",
        )
        == second_stamp
    )
    assert not state.procedure_requires_rerun(
        "GL001",
        "dataset-1",
    )

