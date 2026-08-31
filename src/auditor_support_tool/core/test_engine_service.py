"""Central orchestration service for executable audit procedures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from auditor_support_tool.core.audit_execution_models import (
    AuditExecutionRequest,
    AuditExecutionStatus,
    ExecutionCancellationToken,
)
from auditor_support_tool.core.audit_execution_service import (
    AuditExecutionConflictError,
    AuditExecutionService,
)
from auditor_support_tool.core.audit_procedure_models import (
    ProcedureResult,
    ProcedureRunContext,
)
from auditor_support_tool.core.audit_record_source import (
    AuditRecordSource,
)
from auditor_support_tool.core.audit_run_context_service import (
    AuditRunContextError,
    AuditRunContextService,
)
from auditor_support_tool.core.procedure_dataset_resolution import (
    ProcedureDatasetBundle,
    ProcedureDatasetResolver,
    ProcedureDatasetSource,
)
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)
from auditor_support_tool.core.procedure_parameter_service import (
    ProcedureParameterValidationError,
    resolve_procedure_parameters,
)
from auditor_support_tool.core.procedure_readiness import (
    ProcedureReadinessService,
)
from auditor_support_tool.core.procedure_registry import (
    ProcedureRegistry,
)
from auditor_support_tool.core.test_engine_models import (
    TestEngineOutcome,
    TestEngineStatus,
)


class TestEngineService:
    """Coordinate procedure lookup, readiness, context and execution."""

    def __init__(
        self,
        *,
        registry: ProcedureRegistry,
        readiness_service: ProcedureReadinessService | None = None,
        dataset_resolver: ProcedureDatasetResolver | None = None,
        run_context_service: AuditRunContextService | None = None,
        execution_service: AuditExecutionService | None = None,
    ) -> None:
        self._registry = registry
        self._readiness_service = readiness_service or ProcedureReadinessService()
        self._dataset_resolver = dataset_resolver or ProcedureDatasetResolver()
        self._run_context_service = run_context_service or AuditRunContextService()
        self._execution_service = execution_service or AuditExecutionService()

    def run(
        self,
        *,
        procedure_id: str,
        source: AuditRecordSource,
        source_path: str | Path,
        audit_period_start: str = "",
        audit_period_end: str = "",
        parameters: Mapping[str, object] | None = None,
        dataset_sources: Iterable[ProcedureDatasetSource] = (),
        cancellation_token: ExecutionCancellationToken | None = None,
    ) -> TestEngineOutcome:
        """Run one registered procedure through the complete engine pipeline."""

        canonical_id = canonical_procedure_id(procedure_id)

        procedure = self._registry.get(canonical_id)

        if procedure is None:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.NOT_IMPLEMENTED,
                error_message=(f"No executable implementation is registered for {canonical_id}."),
            )

        definition = procedure.definition

        execution_source: AuditRecordSource = source

        if definition.uses_dataset_requirements:
            dataset_sources_tuple = tuple(dataset_sources)
            active_candidates = tuple(
                candidate
                for candidate in dataset_sources_tuple
                if candidate.source.dataset_id == source.dataset_id
            )

            if len(active_candidates) != 1:
                return TestEngineOutcome(
                    procedure_id=canonical_id,
                    dataset_id=source.dataset_id,
                    status=TestEngineStatus.FAILED,
                    error_message=(
                        "Dataset-aware procedure execution requires exactly one "
                        "mapped dataset descriptor for the active dataset."
                    ),
                )

            active_source = ProcedureDatasetSource.create(
                dataset_type=active_candidates[0].dataset_type,
                source=source,
            )
            resolution = self._dataset_resolver.resolve(
                definition=definition,
                active_source=active_source,
                available_sources=dataset_sources_tuple,
            )
            readiness = self._readiness_service.check_datasets(
                definition=definition,
                resolution=resolution,
            )

            if readiness.can_run:
                execution_source = ProcedureDatasetBundle.create(resolution)
        else:
            readiness = self._readiness_service.check(
                definition=definition,
                source=source,
            )

        if not readiness.can_run:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.BLOCKED,
                readiness=readiness,
                error_message=(
                    "The procedure cannot run because required datasets or "
                    "standard fields are unavailable."
                ),
            )

        try:
            resolved_parameters = resolve_procedure_parameters(
                definition,
                parameters,
            )
        except ProcedureParameterValidationError as error:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.FAILED,
                readiness=readiness,
                error_message=str(error),
            )

        request = AuditExecutionRequest.create(
            procedure_id=canonical_id,
            dataset_id=source.dataset_id,
        )

        try:
            context = self._run_context_service.build(
                request=request,
                record_source=execution_source,
                source_path=source_path,
                procedure_version=(definition.procedure_version),
                audit_period_start=audit_period_start,
                audit_period_end=audit_period_end,
                parameters=resolved_parameters,
            )
        except (
            AuditRunContextError,
            ValueError,
        ) as error:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.FAILED,
                readiness=readiness,
                error_message=str(error),
            )

        def runner(
            supplied_source: AuditRecordSource,
            token: ExecutionCancellationToken,
        ) -> ProcedureResult:
            result = procedure.run(
                context=context,
                source=supplied_source,
                cancellation_token=token,
            )

            self._validate_result(
                result=result,
                context=context,
                source=supplied_source,
            )

            return result

        try:
            execution = self._execution_service.execute(
                request=request,
                source=execution_source,
                runner=runner,
                cancellation_token=cancellation_token,
            )
        except AuditExecutionConflictError as error:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.FAILED,
                readiness=readiness,
                error_message=str(error),
            )

        if execution.status == AuditExecutionStatus.CANCELLED:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.CANCELLED,
                readiness=readiness,
                execution=execution,
                error_message=execution.error_message,
            )

        if execution.status == AuditExecutionStatus.FAILED:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.FAILED,
                readiness=readiness,
                execution=execution,
                error_message=execution.error_message,
            )

        if execution.status != AuditExecutionStatus.COMPLETED:
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.FAILED,
                readiness=readiness,
                execution=execution,
                error_message=(
                    f"The execution service returned an unexpected status: {execution.status}."
                ),
            )

        result = execution.payload

        if not isinstance(
            result,
            ProcedureResult,
        ):
            return TestEngineOutcome(
                procedure_id=canonical_id,
                dataset_id=source.dataset_id,
                status=TestEngineStatus.FAILED,
                readiness=readiness,
                execution=execution,
                error_message=("The procedure did not return a valid ProcedureResult."),
            )

        return TestEngineOutcome(
            procedure_id=canonical_id,
            dataset_id=source.dataset_id,
            status=TestEngineStatus.COMPLETED,
            readiness=readiness,
            execution=execution,
            result=result,
        )

    @staticmethod
    def _validate_result(
        *,
        result: object,
        context: ProcedureRunContext,
        source: AuditRecordSource,
    ) -> None:
        """Validate cross-component invariants for a procedure result."""

        if not isinstance(
            result,
            ProcedureResult,
        ):
            raise TypeError("Audit procedures must return a ProcedureResult.")

        if result.context.execution_id != context.execution_id:
            raise ValueError(
                "Procedure result execution identifier does not match the active run context."
            )

        if result.context.procedure_id != context.procedure_id:
            raise ValueError("Procedure result identifier does not match the active run context.")

        if result.context.dataset_id != context.dataset_id:
            raise ValueError("Procedure result dataset does not match the active run context.")

        if result.population_count != source.record_count:
            raise ValueError(
                "Procedure result population count does not match the audit record source."
            )

        expected_excluded = result.population_count - result.records_evaluated_count

        if result.excluded_record_count != expected_excluded:
            raise ValueError("Procedure result excluded-record count does not reconcile.")

        if sum(result.exclusion_counts.values()) != result.excluded_record_count:
            raise ValueError(
                "Procedure result exclusion reasons do not reconcile to excluded records."
            )

        if result.exception_count != len(result.exception_records):
            raise ValueError(
                "Procedure result exception count does not match its exception records."
            )

        if result.exception_count > result.records_evaluated_count:
            raise ValueError("Procedure result exception count cannot exceed records evaluated.")
