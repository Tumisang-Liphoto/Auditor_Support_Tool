"""Tests for audit-procedure availability filtering."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from auditor_support_tool.core.procedure_availability import (
    ProcedureAvailabilityService,
)


@dataclass(frozen=True)
class StubDefinition:
    """Minimal definition used by availability tests."""

    procedure_id: str


@dataclass(frozen=True)
class StubProcedure:
    """Minimal implemented procedure used by availability tests."""

    definition: StubDefinition


class StubReadinessService:
    """Return deterministic readiness based on procedure identity."""

    def __init__(
        self,
        *,
        runnable_ids: set[str],
        warning_ids: set[str] | None = None,
    ) -> None:
        self._runnable_ids = set(runnable_ids)
        self._warning_ids = set(warning_ids or set())

    def check(
        self,
        *,
        definition: StubDefinition,
        source: object,
    ) -> SimpleNamespace:
        del source

        can_run = definition.procedure_id in self._runnable_ids

        return SimpleNamespace(
            can_run=can_run,
            status=(
                "ready_with_warning"
                if definition.procedure_id in self._warning_ids
                else ("ready" if can_run else "blocked")
            ),
        )


def _procedures() -> tuple[StubProcedure, ...]:
    return (
        StubProcedure(StubDefinition("GL003")),
        StubProcedure(StubDefinition("GL006")),
        StubProcedure(StubDefinition("GL011")),
    )


def test_blocked_procedures_are_not_returned() -> None:
    """Missing required fields must make a procedure invisible to the UI."""

    service = ProcedureAvailabilityService(
        readiness_service=StubReadinessService(
            runnable_ids={"GL003"},
        )
    )

    available = service.available(
        procedures=_procedures(),
        source=object(),
    )

    assert tuple(item.procedure.definition.procedure_id for item in available) == ("GL003",)


def test_ready_with_warning_procedures_remain_available() -> None:
    """Missing optional/helpful fields must not hide a runnable procedure."""

    service = ProcedureAvailabilityService(
        readiness_service=StubReadinessService(
            runnable_ids={"GL003", "GL006"},
            warning_ids={"GL006"},
        )
    )

    available = service.available(
        procedures=_procedures(),
        source=object(),
    )

    assert tuple(item.procedure.definition.procedure_id for item in available) == (
        "GL003",
        "GL006",
    )
    assert available[1].readiness.status == "ready_with_warning"


def test_available_procedures_preserve_registry_order() -> None:
    """Availability filtering must not reorder registered procedures."""

    service = ProcedureAvailabilityService(
        readiness_service=StubReadinessService(
            runnable_ids={"GL006", "GL011"},
        )
    )

    available = service.available(
        procedures=_procedures(),
        source=object(),
    )

    assert tuple(item.procedure.definition.procedure_id for item in available) == (
        "GL006",
        "GL011",
    )


def test_all_blocked_procedures_return_an_empty_result() -> None:
    """A dataset supporting no registered tests should expose no procedures."""

    service = ProcedureAvailabilityService(
        readiness_service=StubReadinessService(
            runnable_ids=set(),
        )
    )

    available = service.available(
        procedures=_procedures(),
        source=object(),
    )

    assert available == ()
