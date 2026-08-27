"""Tests for persistent successful procedure execution stamps."""

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureRunContext,
)
from auditor_support_tool.core.procedure_execution_models import (
    ProcedureExecutionStamp,
)


def create_context(
    *,
    procedure_id: str = "GL003",
    dataset_id: str = "dataset-1",
    parameters: dict[str, object] | None = None,
) -> ProcedureRunContext:
    """Return a reproducible successful run context."""

    request = AuditExecutionRequest.create(
        procedure_id=procedure_id,
        dataset_id=dataset_id,
    )

    return ProcedureRunContext.create(
        request=request,
        procedure_version="1.0",
        source_sha256="a" * 64,
        mapping_fingerprint="b" * 64,
        audit_period_start="2026-01-01",
        audit_period_end="2026-12-31",
        parameters=parameters or {},
    )


def test_execution_stamp_preserves_reproducibility_context() -> None:
    """A successful context should persist all comparison inputs."""

    context = create_context(
        parameters={
            "weekend_days": (
                "Saturday",
                "Sunday",
            ),
        }
    )

    stamp = ProcedureExecutionStamp.from_context(context)

    assert stamp.procedure_id == "GL003"
    assert stamp.dataset_id == "dataset-1"
    assert stamp.procedure_version == "1.0"
    assert stamp.source_sha256 == "a" * 64
    assert stamp.mapping_fingerprint == "b" * 64
    assert stamp.audit_period_start == "2026-01-01"
    assert stamp.audit_period_end == "2026-12-31"
    assert stamp.parameters == {
        "weekend_days": [
            "Saturday",
            "Sunday",
        ]
    }
    assert stamp.completed_at == context.created_at


def test_execution_stamp_round_trips_through_workspace_data() -> None:
    """Saved execution metadata should restore without changing meaning."""

    original = ProcedureExecutionStamp.from_context(
        create_context(
            parameters={
                "weekend_days": [
                    "Saturday",
                ],
            }
        )
    )

    restored = ProcedureExecutionStamp.from_dict(original.to_dict())

    assert restored == original
