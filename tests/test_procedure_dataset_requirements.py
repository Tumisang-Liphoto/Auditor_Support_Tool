"""Tests for generic multi-dataset procedure requirements."""

import pytest

from auditor_support_tool.core.procedure_dataset_models import (
    ProcedureDatasetRequirement,
)
from auditor_support_tool.core.procedure_definition import (
    ProcedureDefinition,
)
from auditor_support_tool.core.workbook_package import DatasetType
from auditor_support_tool.domains.financial_audit.general_ledger.procedure_catalogue import (
    require_general_ledger_procedure,
)


def _requirement(
    *,
    role: str = "primary_data",
    dataset_type: DatasetType = DatasetType.GENERAL_LEDGER,
    primary: bool = True,
) -> ProcedureDatasetRequirement:
    return ProcedureDatasetRequirement.create(
        role=role,
        dataset_type=dataset_type,
        required_fields=("account_code",),
        helpful_fields=("transaction_amount",),
        primary=primary,
    )


def test_dataset_requirement_normalises_role_and_fields() -> None:
    """Dataset requirements should expose stable role and field metadata."""

    requirement = ProcedureDatasetRequirement.create(
        role="  General_Ledger  ",
        dataset_type=DatasetType.GENERAL_LEDGER,
        required_fields=(" account_code ",),
        helpful_fields=(" transaction_amount ",),
        primary=True,
    )

    assert requirement.role == "general_ledger"
    assert requirement.required_fields == ("account_code",)
    assert requirement.helpful_fields == ("transaction_amount",)
    assert requirement.all_fields == (
        "account_code",
        "transaction_amount",
    )
    assert requirement.primary is True


def test_dataset_requirement_rejects_unclassified_dataset_type() -> None:
    """Executable requirements must identify a meaningful dataset type."""

    with pytest.raises(
        ValueError,
        match="unclassified",
    ):
        ProcedureDatasetRequirement.create(
            role="reference",
            dataset_type=DatasetType.UNCLASSIFIED,
        )


def test_dataset_requirement_rejects_field_overlap() -> None:
    """A field cannot be both mandatory and optional for one dataset role."""

    with pytest.raises(
        ValueError,
        match="both required and helpful",
    ):
        ProcedureDatasetRequirement.create(
            role="primary",
            dataset_type=DatasetType.GENERAL_LEDGER,
            required_fields=("account_code",),
            helpful_fields=("account_code",),
            primary=True,
        )


def test_definition_retains_legacy_single_dataset_field_contract() -> None:
    """Existing procedures should remain backward compatible."""

    definition = ProcedureDefinition.create(
        procedure_id="GL003",
        name="Weekend Transactions",
        category="General Ledger",
        required_fields=("transaction_date",),
        helpful_fields=("journal_number",),
    )

    assert definition.dataset_requirements == ()
    assert definition.uses_dataset_requirements is False
    assert definition.is_multi_dataset is False
    assert definition.primary_dataset_requirement is None
    assert definition.all_fields == (
        "transaction_date",
        "journal_number",
    )


def test_dataset_aware_definition_requires_exactly_one_primary() -> None:
    """Multi-dataset procedures need one authoritative primary population."""

    first = _requirement(
        role="general_ledger",
        primary=False,
    )
    second = _requirement(
        role="chart_of_accounts",
        dataset_type=DatasetType.CHART_OF_ACCOUNTS,
        primary=False,
    )

    with pytest.raises(
        ValueError,
        match="exactly one primary",
    ):
        ProcedureDefinition.create(
            procedure_id="GL011",
            name="Unmapped Accounts",
            category="General Ledger",
            dataset_requirements=(
                first,
                second,
            ),
        )


def test_dataset_aware_definition_rejects_duplicate_roles() -> None:
    """Roles must uniquely identify sources supplied to a procedure."""

    first = _requirement(
        role="reference",
        primary=True,
    )
    second = _requirement(
        role="reference",
        dataset_type=DatasetType.CHART_OF_ACCOUNTS,
        primary=False,
    )

    with pytest.raises(
        ValueError,
        match="role is duplicated",
    ):
        ProcedureDefinition.create(
            procedure_id="GL011",
            name="Unmapped Accounts",
            category="General Ledger",
            dataset_requirements=(
                first,
                second,
            ),
        )


def test_dataset_aware_definition_rejects_legacy_field_lists() -> None:
    """Dataset-aware definitions should not mix two field-location models."""

    requirement = _requirement()

    with pytest.raises(
        ValueError,
        match="inside dataset requirements",
    ):
        ProcedureDefinition.create(
            procedure_id="GL011",
            name="Unmapped Accounts",
            category="General Ledger",
            required_fields=("account_code",),
            dataset_requirements=(requirement,),
        )


def test_gl011_declares_general_ledger_and_chart_of_accounts() -> None:
    """GL-011 should now describe its two required dataset roles."""

    definition = require_general_ledger_procedure("GL011").definition

    assert definition.uses_dataset_requirements is True
    assert definition.is_multi_dataset is True
    assert definition.required_fields == ()
    assert definition.helpful_fields == ()

    assert tuple(
        (
            requirement.role,
            requirement.dataset_type,
            requirement.required_fields,
            requirement.primary,
        )
        for requirement in definition.dataset_requirements
    ) == (
        (
            "general_ledger",
            DatasetType.GENERAL_LEDGER,
            ("account_code",),
            True,
        ),
        (
            "chart_of_accounts",
            DatasetType.CHART_OF_ACCOUNTS,
            ("account_code",),
            False,
        ),
    )

    assert definition.primary_dataset_requirement is not None
    assert definition.primary_dataset_requirement.role == "general_ledger"


def test_dataset_aware_all_fields_is_deterministic() -> None:
    """Flattened field metadata should remain useful for generic consumers."""

    definition = ProcedureDefinition.create(
        procedure_id="GL011",
        name="Unmapped Accounts",
        category="General Ledger",
        dataset_requirements=(
            ProcedureDatasetRequirement.create(
                role="general_ledger",
                dataset_type=DatasetType.GENERAL_LEDGER,
                required_fields=("account_code",),
                helpful_fields=("transaction_amount",),
                primary=True,
            ),
            ProcedureDatasetRequirement.create(
                role="chart_of_accounts",
                dataset_type=DatasetType.CHART_OF_ACCOUNTS,
                required_fields=("account_code",),
                helpful_fields=("account_name",),
            ),
        ),
    )

    assert definition.all_fields == (
        "account_code",
        "transaction_amount",
        "account_name",
    )
