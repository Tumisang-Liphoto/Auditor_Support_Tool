"""Registry of executable audit-procedure implementations."""

from __future__ import annotations

from collections.abc import Iterable

from auditor_support_tool.core.audit_procedure import (
    AuditProcedure,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.procedure_identity import (
    canonical_procedure_id,
)


class ProcedureRegistrationError(ValueError):
    """Raised when a procedure cannot be registered safely."""


class ProcedureNotRegisteredError(KeyError):
    """Raised when an executable procedure is not registered."""


class ProcedureRegistry:
    """Store and resolve executable audit procedures by canonical identity."""

    def __init__(self) -> None:
        self._procedures: dict[str, AuditProcedure] = {}

    @property
    def procedures(self) -> tuple[AuditProcedure, ...]:
        """Return registered procedures in registration order."""

        return tuple(self._procedures.values())

    @property
    def definitions(self) -> tuple[ProcedureDefinition, ...]:
        """Return definitions for all registered executable procedures."""

        return tuple(procedure.definition for procedure in self._procedures.values())

    def register(
        self,
        procedure: AuditProcedure,
    ) -> None:
        """Register one executable procedure."""

        definition = getattr(
            procedure,
            "definition",
            None,
        )

        if not isinstance(
            definition,
            ProcedureDefinition,
        ):
            raise ProcedureRegistrationError(
                "Registered procedures must expose a ProcedureDefinition through 'definition'."
            )

        runner = getattr(
            procedure,
            "run",
            None,
        )

        if not callable(runner):
            raise ProcedureRegistrationError(
                "Registered procedures must provide a callable 'run' method."
            )

        procedure_id = definition.procedure_id

        if procedure_id in self._procedures:
            raise ProcedureRegistrationError(
                f"An executable procedure is already registered for {definition.display_id}."
            )

        self._procedures[procedure_id] = procedure

    def register_many(
        self,
        procedures: Iterable[AuditProcedure],
    ) -> None:
        """Register multiple executable procedures."""

        for procedure in procedures:
            self.register(procedure)

    def get(
        self,
        procedure_id: str,
    ) -> AuditProcedure | None:
        """Return a registered procedure or ``None`` when unavailable."""

        try:
            canonical = canonical_procedure_id(procedure_id)
        except ValueError:
            return None

        return self._procedures.get(canonical)

    def require(
        self,
        procedure_id: str,
    ) -> AuditProcedure:
        """Return a registered procedure or raise a clear lookup error."""

        canonical = canonical_procedure_id(procedure_id)

        procedure = self._procedures.get(canonical)

        if procedure is None:
            raise ProcedureNotRegisteredError(
                f"No executable audit procedure is registered for {canonical}."
            )

        return procedure

    def is_registered(
        self,
        procedure_id: str,
    ) -> bool:
        """Return whether an executable procedure is registered."""

        return self.get(procedure_id) is not None
