"""Generic presentation contracts for audit procedure results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DashboardMetric:
    """One headline result metric."""

    title: str
    value: str
    detail: str
    icon_name: str
    emphasis: str = "normal"


@dataclass(frozen=True, slots=True)
class DashboardIndicator:
    """One additional risk indicator displayed to the auditor."""

    title: str
    value: str
    detail: str
    available: bool = True


@dataclass(frozen=True, slots=True)
class DashboardSummaryRow:
    """One row in a compact analytical summary."""

    label: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Compact tabular analysis presented above exception detail."""

    title: str
    description: str
    headers: tuple[str, ...]
    rows: tuple[DashboardSummaryRow, ...]


@dataclass(frozen=True, slots=True)
class DashboardTableColumn:
    """One column in the reusable exception explorer."""

    key: str
    label: str


@dataclass(frozen=True, slots=True)
class DashboardTableFilter:
    """One named exception-table filter."""

    key: str
    label: str


@dataclass(frozen=True, slots=True)
class DashboardTableRow:
    """One source-linked row prepared for result display."""

    values: dict[str, str]
    groups: frozenset[str] = field(default_factory=lambda: frozenset({"all"}))


@dataclass(frozen=True, slots=True)
class DashboardTable:
    """Reusable exception explorer presentation."""

    title: str
    description: str
    columns: tuple[DashboardTableColumn, ...]
    rows: tuple[DashboardTableRow, ...]
    filters: tuple[DashboardTableFilter, ...]
    source_note: str


@dataclass(frozen=True, slots=True)
class ResultDashboardPresentation:
    """Procedure-neutral dashboard consumed by the Results page."""

    metrics: tuple[DashboardMetric, ...]
    risk_title: str
    risk_description: str
    risk_indicators: tuple[DashboardIndicator, ...]
    summary: DashboardSummary | None
    observations: tuple[str, ...]
    attention_areas: tuple[str, ...]
    table: DashboardTable
    audit_use_statement: str
