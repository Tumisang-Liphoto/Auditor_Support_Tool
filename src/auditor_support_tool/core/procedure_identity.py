"""Canonical audit-procedure identifier helpers."""

from __future__ import annotations

import re

_CANONICAL_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{2})(?P<number>\d{3})$")
_DISPLAY_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{2})-(?P<number>\d{3})$")


def canonical_procedure_id(value: str) -> str:
    """Return a canonical compact procedure ID such as ``GL003``.

    Accepted inputs are canonical IDs (``GL003``) and their display form
    (``GL-003``). Legacy methodology references are deliberately rejected
    because their numbering conflicts with the current engine catalogue.
    """

    cleaned = value.strip().upper()

    canonical_match = _CANONICAL_PATTERN.fullmatch(cleaned)

    if canonical_match is not None:
        return cleaned

    display_match = _DISPLAY_PATTERN.fullmatch(cleaned)

    if display_match is not None:
        return f"{display_match.group('prefix')}{display_match.group('number')}"

    raise ValueError(
        "Procedure identifier must use the engine catalogue format "
        "'GL003' or display format 'GL-003'. Legacy FA-GL references "
        "must be reconciled explicitly rather than converted automatically."
    )


def procedure_display_id(value: str) -> str:
    """Return the user-facing display form of an engine procedure ID."""

    canonical = canonical_procedure_id(value)

    return f"{canonical[:2]}-{canonical[2:]}"
