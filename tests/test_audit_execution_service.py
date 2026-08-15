"""Tests for guarded audit-procedure execution."""

from __future__ import annotations

from collections.abc import Iterator
from threading import Event, Thread

import pytest

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionCancelledError,
    AuditExecutionRequest,
    AuditExecutionStatus,
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_execution_service import (
    AuditExecutionConflictError,
    AuditExecutionService,
    AuditExecutionSourceError,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)


class StubRecord:
    """Minimal generic record used by execution-service tests."""

    def __init__(
        self,
        record_number: int,
    ) -> None:
        self.record_number = record_number


class StubRecordSource:
    """Generic non-domain record source used by execution-service tests."""

    def __init__(
        self,
        *,
        dataset_id: str = "dataset-123",
        record_count: int = 5,
    ) -> None:
        self._dataset_id = dataset_id
        self._records = tuple(StubRecord(index + 1) for index in range(record_count))

    @property
    def dataset_id(self) -> str:
        """Return the stable test dataset identifier."""

        return self._dataset_id

    @property
    def record_count(self) -> int:
        """Return the complete test population count."""

        return len(self._records)

    @property
    def standard_fields(self) -> tuple[str, ...]:
        """Return the fields exposed by this generic source."""

        return ()

    @property
    def mapping_fingerprint(self) -> str:
        """Return a deterministic placeholder mapping fingerprint."""

        return "a" * 64

    def has_field(
        self,
        standard_field_key: str,
    ) -> bool:
        """Return whether a field is available."""

        return standard_field_key in self.standard_fields

    def iter_records(self) -> Iterator[StubRecord]:
        """Yield the complete test population."""

        yield from self._records


def create_source(
    record_count: int = 5,
    *,
    dataset_id: str = "dataset-123",
) -> StubRecordSource:
    """Create a generic audit record source."""

    return StubRecordSource(
        dataset_id=dataset_id,
        record_count=record_count,
    )


def create_request(
    *,
    dataset_id: str = "dataset-123",
) -> AuditExecutionRequest:
    """Create a standard test execution request."""

    return AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id=dataset_id,
    )


def test_request_requires_procedure_identifier() -> None:
    """Execution requests require a procedure identifier."""

    with pytest.raises(
        ValueError,
        match="Procedure identifier",
    ):
        AuditExecutionRequest.create(
            procedure_id=" ",
            dataset_id="dataset-123",
        )


def test_full_record_source_is_passed_without_materialisation() -> None:
    """Execution should pass the complete source directly to the runner."""

    source = create_source(record_count=250)
    request = create_request()
    service = AuditExecutionService()

    received_source: AuditRecordSource | None = None

    def runner(
        supplied_source: AuditRecordSource,
        token: ExecutionCancellationToken,
    ) -> object:
        nonlocal received_source
        received_source = supplied_source

        assert not token.is_cancelled

        records_seen = sum(1 for _record in supplied_source.iter_records())

        return {
            "records_seen": records_seen,
        }

    outcome = service.execute(
        request=request,
        source=source,
        runner=runner,
    )

    assert received_source is source
    assert outcome.status == AuditExecutionStatus.COMPLETED
    assert outcome.source_record_count == 250
    assert outcome.payload == {
        "records_seen": 250,
    }


def test_execution_rejects_wrong_dataset_source() -> None:
    """A request cannot execute against a different dataset."""

    source = create_source(
        dataset_id="dataset-other",
    )
    request = create_request(
        dataset_id="dataset-123",
    )
    service = AuditExecutionService()

    with pytest.raises(
        AuditExecutionSourceError,
        match="does not match",
    ):
        service.execute(
            request=request,
            source=source,
            runner=lambda supplied_source, token: None,
        )


def test_execution_duration_is_recorded() -> None:
    """Every execution should produce traceable timing information."""

    source = create_source()
    request = create_request()
    service = AuditExecutionService()

    outcome = service.execute(
        request=request,
        source=source,
        runner=lambda supplied_source, token: supplied_source.record_count,
    )

    assert outcome.started_at
    assert outcome.finished_at
    assert outcome.duration_seconds >= 0.0


def test_pre_cancelled_execution_does_not_call_runner() -> None:
    """Cancellation before execution should prevent procedure work."""

    source = create_source()
    request = create_request()
    service = AuditExecutionService()
    token = ExecutionCancellationToken()
    token.cancel()

    runner_called = False

    def runner(
        supplied_source: AuditRecordSource,
        supplied_token: ExecutionCancellationToken,
    ) -> object:
        nonlocal runner_called
        runner_called = True

        return supplied_source.record_count

    outcome = service.execute(
        request=request,
        source=source,
        runner=runner,
        cancellation_token=token,
    )

    assert not runner_called
    assert outcome.status == AuditExecutionStatus.CANCELLED


def test_cooperative_cancellation_is_reported() -> None:
    """A runner may stop cooperatively when cancellation is requested."""

    source = create_source(record_count=10)
    request = create_request()
    service = AuditExecutionService()
    token = ExecutionCancellationToken()

    def runner(
        supplied_source: AuditRecordSource,
        supplied_token: ExecutionCancellationToken,
    ) -> object:
        for index, _record in enumerate(supplied_source.iter_records()):
            if index == 3:
                supplied_token.cancel()

            supplied_token.raise_if_cancelled()

        return None

    outcome = service.execute(
        request=request,
        source=source,
        runner=runner,
        cancellation_token=token,
    )

    assert outcome.status == AuditExecutionStatus.CANCELLED


def test_runner_failure_is_captured() -> None:
    """Procedure exceptions should become controlled failed outcomes."""

    source = create_source()
    request = create_request()
    service = AuditExecutionService()

    def runner(
        supplied_source: AuditRecordSource,
        token: ExecutionCancellationToken,
    ) -> object:
        raise RuntimeError("Procedure failed.")

    outcome = service.execute(
        request=request,
        source=source,
        runner=runner,
    )

    assert outcome.status == AuditExecutionStatus.FAILED
    assert outcome.error_message == "Procedure failed."


def test_duplicate_execution_is_prevented() -> None:
    """The same procedure and dataset cannot run concurrently."""

    source = create_source()
    request = create_request()
    service = AuditExecutionService()

    runner_started = Event()
    runner_release = Event()
    first_outcome: list[object] = []

    def blocking_runner(
        supplied_source: AuditRecordSource,
        token: ExecutionCancellationToken,
    ) -> object:
        runner_started.set()
        runner_release.wait(timeout=5)

        return supplied_source.record_count

    def execute_first() -> None:
        first_outcome.append(
            service.execute(
                request=request,
                source=source,
                runner=blocking_runner,
            )
        )

    thread = Thread(
        target=execute_first,
        daemon=True,
    )
    thread.start()

    assert runner_started.wait(timeout=5)

    assert service.is_running(
        procedure_id=request.procedure_id,
        dataset_id=request.dataset_id,
    )

    with pytest.raises(
        AuditExecutionConflictError,
        match="already running",
    ):
        service.execute(
            request=AuditExecutionRequest.create(
                procedure_id=request.procedure_id,
                dataset_id=request.dataset_id,
            ),
            source=source,
            runner=lambda supplied_source, token: None,
        )

    runner_release.set()
    thread.join(timeout=5)

    assert len(first_outcome) == 1

    assert not service.is_running(
        procedure_id=request.procedure_id,
        dataset_id=request.dataset_id,
    )


def test_cancellation_exception_type_is_controlled() -> None:
    """The cancellation token should raise the dedicated exception type."""

    token = ExecutionCancellationToken()
    token.cancel()

    with pytest.raises(AuditExecutionCancelledError):
        token.raise_if_cancelled()
