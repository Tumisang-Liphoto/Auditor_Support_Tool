"""Tests for guarded audit-procedure execution."""

from pathlib import Path
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
)
from auditor_support_tool.domains.financial_audit.general_ledger.models import (
    LoadedTable,
    PopulationSummary,
)


def create_table(
    record_count: int = 5,
) -> LoadedTable:
    """Create a loaded audit population without reading a source file."""

    rows = tuple(
        {
            "Transaction Date": f"2026-01-{index + 1:02d}",
            "Amount": float(index + 1),
        }
        for index in range(record_count)
    )

    return LoadedTable(
        source_path=Path("population.xlsx"),
        file_type="xlsx",
        worksheet_name="General_Ledger",
        headers=("Transaction Date", "Amount"),
        original_headers=("Transaction Date", "Amount"),
        rows=rows,
        summary=PopulationSummary(
            source_records_read=record_count,
            records_loaded=record_count,
            blank_rows_skipped=0,
            column_count=2,
            blank_cell_count=0,
            header_changes=(),
        ),
    )


def create_request() -> AuditExecutionRequest:
    """Create a standard test execution request."""

    return AuditExecutionRequest.create(
        procedure_id="GL003",
        dataset_id="dataset-123",
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


def test_full_population_is_passed_without_truncation() -> None:
    """The execution service must pass the complete LoadedTable to a procedure."""

    table = create_table(record_count=250)
    request = create_request()
    service = AuditExecutionService()

    received_table: LoadedTable | None = None

    def runner(
        supplied_table: LoadedTable,
        token: ExecutionCancellationToken,
    ) -> object:
        nonlocal received_table
        received_table = supplied_table

        assert not token.is_cancelled

        return {
            "records_seen": supplied_table.record_count,
        }

    outcome = service.execute(
        request=request,
        table=table,
        runner=runner,
    )

    assert received_table is table
    assert received_table.rows is table.rows
    assert outcome.status == AuditExecutionStatus.COMPLETED
    assert outcome.source_record_count == 250
    assert outcome.payload == {"records_seen": 250}


def test_execution_duration_is_recorded() -> None:
    """Every execution should produce traceable timing information."""

    table = create_table()
    request = create_request()
    service = AuditExecutionService()

    outcome = service.execute(
        request=request,
        table=table,
        runner=lambda supplied_table, token: supplied_table.record_count,
    )

    assert outcome.started_at
    assert outcome.finished_at
    assert outcome.duration_seconds >= 0.0


def test_pre_cancelled_execution_does_not_call_runner() -> None:
    """Cancellation before execution should prevent procedure work."""

    table = create_table()
    request = create_request()
    service = AuditExecutionService()
    token = ExecutionCancellationToken()
    token.cancel()

    runner_called = False

    def runner(
        supplied_table: LoadedTable,
        supplied_token: ExecutionCancellationToken,
    ) -> object:
        nonlocal runner_called
        runner_called = True
        return supplied_table.record_count

    outcome = service.execute(
        request=request,
        table=table,
        runner=runner,
        cancellation_token=token,
    )

    assert not runner_called
    assert outcome.status == AuditExecutionStatus.CANCELLED


def test_cooperative_cancellation_is_reported() -> None:
    """A runner may stop cooperatively when cancellation is requested."""

    table = create_table(record_count=10)
    request = create_request()
    service = AuditExecutionService()
    token = ExecutionCancellationToken()

    def runner(
        supplied_table: LoadedTable,
        supplied_token: ExecutionCancellationToken,
    ) -> object:
        for index, _row in enumerate(supplied_table.rows):
            if index == 3:
                supplied_token.cancel()

            supplied_token.raise_if_cancelled()

        return None

    outcome = service.execute(
        request=request,
        table=table,
        runner=runner,
        cancellation_token=token,
    )

    assert outcome.status == AuditExecutionStatus.CANCELLED


def test_runner_failure_is_captured() -> None:
    """Procedure exceptions should become controlled failed outcomes."""

    table = create_table()
    request = create_request()
    service = AuditExecutionService()

    def runner(
        supplied_table: LoadedTable,
        token: ExecutionCancellationToken,
    ) -> object:
        raise RuntimeError("Procedure failed.")

    outcome = service.execute(
        request=request,
        table=table,
        runner=runner,
    )

    assert outcome.status == AuditExecutionStatus.FAILED
    assert outcome.error_message == "Procedure failed."


def test_duplicate_execution_is_prevented() -> None:
    """The same procedure and dataset cannot run concurrently."""

    table = create_table()
    request = create_request()
    service = AuditExecutionService()

    runner_started = Event()
    runner_release = Event()
    first_outcome: list[object] = []

    def blocking_runner(
        supplied_table: LoadedTable,
        token: ExecutionCancellationToken,
    ) -> object:
        runner_started.set()
        runner_release.wait(timeout=5)
        return supplied_table.record_count

    def execute_first() -> None:
        first_outcome.append(
            service.execute(
                request=request,
                table=table,
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
            table=table,
            runner=lambda supplied_table, token: None,
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
