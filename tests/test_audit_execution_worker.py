"""Behaviour of the page's real background engine pipeline."""

from threading import Event

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QThread
from shiboken6 import isValid

from auditor_support_tool.core.prepared_audit_dataset import PreparedAuditDataset
from auditor_support_tool.core.procedure_execution_status_service import ProcedureExecutionStatus
from auditor_support_tool.core.procedure_registry import ProcedureRegistry
from auditor_support_tool.core.test_engine_models import TestEngineStatus as EngineStatus
from auditor_support_tool.core.workbook_package import FieldMappingStatus
from auditor_support_tool.core.workbook_package_service import WorkbookPackageService
from auditor_support_tool.core.workspace_models import WorkspaceIdentity
from auditor_support_tool.core.workspace_state import WorkspaceState
from auditor_support_tool.gui.pages.audit_procedures_page import AuditProceduresPage
from auditor_support_tool.gui.workers.audit_execution_worker import AuditExecutionWorker
from tests.test_test_engine_service import StubProcedure, create_source_file


class GatedProcedure(StubProcedure):
    def __init__(self):
        super().__init__()
        self.entered = Event()
        self.release = Event()
        self.calls = 0
        self.thread = None

    def run(self, **kwargs):
        self.calls += 1
        self.thread = QThread.currentThread()
        self.entered.set()
        while not self.release.wait(0.01):
            kwargs["cancellation_token"].raise_if_cancelled()
        return super().run(**kwargs)


@pytest.fixture
def execution_page(tmp_path, qtbot):
    path = create_source_file(tmp_path)
    package = WorkbookPackageService().build_package(path)
    dataset = package.datasets[0]
    dataset.mapping_status = FieldMappingStatus.CONFIRMED
    state = WorkspaceState()
    state.start_workspace(WorkspaceIdentity.create(name="Background audit"))
    state.set_workbook_package(package)
    procedure = GatedProcedure()
    registry = ProcedureRegistry()
    registry.register(procedure)
    page = AuditProceduresPage(workspace_state=state, procedure_registry=registry)
    outcomes = []
    page.result_ready.connect(outcomes.append)
    yield page, state, procedure, path, dataset, outcomes
    procedure.release.set()
    for worker in tuple(AuditExecutionWorker._active):
        worker.cancel()
        assert worker.wait(5000)
    QCoreApplication.processEvents()
    if isValid(page):
        page.close()
        page.deleteLater()


def test_engine_and_hashing_run_off_gui_thread_and_duplicate_click_is_ignored(
    execution_page, qtbot, monkeypatch
):
    page, state, procedure, path, dataset, outcomes = execution_page
    hash_threads = []
    integrity = page._test_engine._run_context_service._source_integrity_service
    real_hash = integrity.sha256_file

    def checked_hash(path):
        hash_threads.append(QThread.currentThread())
        return real_hash(path)

    monkeypatch.setattr(integrity, "sha256_file", checked_hash)
    delivery_threads = []
    page.result_ready.connect(lambda _: delivery_threads.append(QThread.currentThread()))
    page._run_procedure("PROC001")
    qtbot.waitUntil(procedure.entered.is_set)
    assert page.is_executing
    assert not page._procedures_container.isEnabled()
    page._run_procedure("PROC001")
    assert procedure.calls == 1
    assert hash_threads and all(thread != page.thread() for thread in hash_threads)
    assert procedure.thread != page.thread()
    procedure.release.set()
    qtbot.waitUntil(lambda: bool(outcomes))
    assert outcomes[-1].status == EngineStatus.COMPLETED
    assert delivery_threads == [page.thread()]
    assert not page.is_executing
    assert page._procedures_container.isEnabled()
    assert state.get_procedure_execution_stamp("PROC001", dataset.dataset_id)
    qtbot.waitUntil(lambda: not AuditExecutionWorker._active)


@pytest.mark.parametrize("prior_success", [False, True])
@pytest.mark.parametrize("attempt", ["failed", "blocked", "cancelled"])
def test_unsuccessful_background_attempt_preserves_rerun_semantics(
    execution_page, qtbot, monkeypatch, prior_success, attempt
):
    page, state, procedure, path, dataset, outcomes = execution_page
    if prior_success:
        procedure.release.set()
        with qtbot.waitSignal(page.result_ready):
            page._run_procedure("PROC001")
    stamp = state.get_procedure_execution_stamp("PROC001", dataset.dataset_id)
    procedure.release.clear()
    procedure.entered.clear()
    if attempt == "failed":
        procedure.behavior = "raise"
        procedure.release.set()
    elif attempt == "blocked":
        from dataclasses import replace

        procedure._definition = replace(procedure.definition, required_fields=("missing",))
    with qtbot.waitSignal(page.result_ready):
        page._run_procedure("PROC001")
        if attempt == "cancelled":
            qtbot.waitUntil(procedure.entered.is_set)
            page._cancel_button.click()
    assert outcomes[-1].status.value == attempt
    assert state.get_procedure_execution_stamp("PROC001", dataset.dataset_id) == stamp
    assert state.procedure_requires_rerun("PROC001", dataset.dataset_id) == prior_success
    if prior_success:
        assert (
            page._procedure_execution_status(
                definition=procedure.definition, source=PreparedAuditDataset(dataset)
            )
            == ProcedureExecutionStatus.NEEDS_RERUN
        )
    # A subsequent success must become authoritative and clear the marker.
    procedure.behavior = "complete"
    from dataclasses import replace

    procedure._definition = replace(procedure.definition, required_fields=())
    procedure.release.set()
    with qtbot.waitSignal(page.result_ready):
        page._run_procedure("PROC001")
    assert outcomes[-1].status == EngineStatus.COMPLETED
    assert not state.procedure_requires_rerun("PROC001", dataset.dataset_id)


@pytest.mark.parametrize("change", ["cache_failure", "source_changed", "source_deleted"])
def test_success_evidence_does_not_depend_on_cache_or_current_file(
    execution_page, qtbot, monkeypatch, change
):
    page, state, procedure, path, dataset, outcomes = execution_page
    if change == "cache_failure":

        def fail_cache(_):
            raise OSError("Cache unavailable")

        monkeypatch.setattr(page._execution_status_service, "refresh_source_hash", fail_cache)
    page._run_procedure("PROC001")
    qtbot.waitUntil(procedure.entered.is_set)
    original_hash = dataset.loaded_table.source_sha256
    if change == "source_changed":
        path.write_text("different,current,source\n", encoding="utf-8")
    elif change == "source_deleted":
        path.unlink()
    procedure.release.set()
    qtbot.waitUntil(lambda: bool(outcomes))
    assert outcomes[-1].status == EngineStatus.COMPLETED
    stamp = state.get_procedure_execution_stamp("PROC001", dataset.dataset_id)
    assert stamp.source_sha256 == original_hash
    status = page._procedure_execution_status(
        definition=procedure.definition, source=PreparedAuditDataset(dataset)
    )
    assert status == (
        ProcedureExecutionStatus.COMPLETED
        if change == "cache_failure"
        else ProcedureExecutionStatus.NEEDS_RERUN
    )


def test_workspace_clear_discards_pending_outcome(execution_page, qtbot):
    page, state, procedure, path, dataset, outcomes = execution_page
    page._run_procedure("PROC001")
    qtbot.waitUntil(procedure.entered.is_set)
    state.clear()
    state.start_workspace(WorkspaceIdentity.create(name="Replacement"))
    qtbot.waitUntil(lambda: not page.is_executing)
    assert not outcomes
    assert not state.procedure_execution_stamps
    assert not state.procedure_rerun_requirements


def test_unexpected_engine_error_releases_page(execution_page, qtbot, monkeypatch):
    page, state, procedure, path, dataset, outcomes = execution_page

    def fail_engine(**kwargs):
        raise RuntimeError("Unexpected failure")

    monkeypatch.setattr(page._test_engine, "run", fail_engine)
    with qtbot.waitSignal(page.result_ready):
        page._run_procedure("PROC001")
    assert outcomes[-1].status == EngineStatus.FAILED
    assert not page.is_executing
    assert page._procedures_container.isEnabled()


def test_page_destruction_cancels_and_releases_worker(execution_page, qtbot):
    page, state, procedure, path, dataset, outcomes = execution_page
    page._run_procedure("PROC001")
    qtbot.waitUntil(procedure.entered.is_set)
    page.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qtbot.waitUntil(lambda: not AuditExecutionWorker._active)
    assert not state.procedure_execution_stamps


def test_cancel_after_engine_completion_does_not_rewrite_success(
    execution_page, qtbot, monkeypatch
):
    page, state, procedure, path, dataset, outcomes = execution_page
    warming = Event()
    release_cache = Event()

    def warm_cache(_):
        warming.set()
        assert release_cache.wait(5)

    monkeypatch.setattr(page._execution_status_service, "refresh_source_hash", warm_cache)
    procedure.release.set()
    page._run_procedure("PROC001")
    qtbot.waitUntil(warming.is_set)
    page.cancel_execution()
    release_cache.set()
    qtbot.waitUntil(lambda: bool(outcomes))
    assert outcomes[-1].status == EngineStatus.COMPLETED
    assert state.get_procedure_execution_stamp("PROC001", dataset.dataset_id)


def test_workspace_transition_waits_for_cancellation(execution_page, qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from tests.test_clear_audit_guard import TransitionWindow

    page, state, procedure, path, dataset, outcomes = execution_page
    window = TransitionWindow(state, None)
    qtbot.addWidget(window)
    window._pages = {"workspace.audit_procedures": page}
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args))
    page._run_procedure("PROC001")
    qtbot.waitUntil(procedure.entered.is_set)
    identity = state.workspace_identity
    assert not window._confirm_workspace_transition()
    assert messages
    assert state.workspace_identity == identity
    qtbot.waitUntil(lambda: bool(outcomes))
    assert outcomes[-1].status == EngineStatus.CANCELLED


def test_source_replacement_preserves_failed_rerun_history(execution_page, qtbot):
    page, state, procedure, path, dataset, outcomes = execution_page
    procedure.release.set()
    with qtbot.waitSignal(page.result_ready):
        page._run_procedure("PROC001")
    stamp = state.get_procedure_execution_stamp("PROC001", dataset.dataset_id)
    procedure.release.clear()
    procedure.entered.clear()
    page._run_procedure("PROC001")
    qtbot.waitUntil(procedure.entered.is_set)
    with qtbot.waitSignal(page.result_ready):
        state.set_source(state.source_info)
    assert outcomes[-1].status == EngineStatus.CANCELLED
    assert state.get_procedure_execution_stamp("PROC001", dataset.dataset_id) == stamp
    assert state.procedure_requires_rerun("PROC001", dataset.dataset_id)


def test_execution_snapshot_detaches_mapping_metadata(execution_page):
    page, state, procedure, path, dataset, outcomes = execution_page
    original_column = dataset.columns[0]
    dataset.field_mappings[original_column.column_id] = "reference"
    snapshot = page._execution_source(dataset)
    fingerprint = snapshot.mapping_fingerprint
    original_column.included = False
    dataset.field_mappings.clear()
    assert snapshot.has_field("reference")
    assert snapshot.column_for_field("reference").included
    assert snapshot.mapping_fingerprint == fingerprint
    assert snapshot.dataset.loaded_table is dataset.loaded_table


def test_worker_preserves_multi_dataset_engine_semantics(tmp_path, qtbot):
    from auditor_support_tool.core.procedure_execution_status_service import (
        ProcedureExecutionStatusService,
    )
    from tests.test_multi_dataset_test_engine import (
        StubMultiDatasetProcedure,
        _engine,
        _source_file,
        _sources,
    )

    procedure = StubMultiDatasetProcedure()
    primary, reference, descriptors = _sources()
    engine = _engine(procedure)
    path = _source_file(tmp_path)
    expected = engine.run(
        procedure_id="PROC011",
        source=primary,
        source_path=path,
        dataset_sources=descriptors,
    )
    worker = AuditExecutionWorker(
        engine=engine,
        procedure_id="PROC011",
        source=primary,
        source_path=path,
        audit_period_start="",
        audit_period_end="",
        parameters={},
        dataset_sources=descriptors,
        status_service=ProcedureExecutionStatusService(),
    )
    with qtbot.waitSignal(worker.finished):
        worker.start()
    assert worker.outcome.status == EngineStatus.COMPLETED
    assert (
        worker.outcome.result.context.mapping_fingerprint
        == expected.result.context.mapping_fingerprint
    )
    assert worker.outcome.result.metrics["reference_population"] == reference.record_count
