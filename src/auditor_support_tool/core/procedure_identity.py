"""Canonical audit-procedure identifier helpers."""

from __future__ import annotations

import re

_CANONICAL_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{2,12})(?P<number>\d{3})$")
_DISPLAY_PATTERN = re.compile(r"^(?P<prefix>[A-Z]{2,12})-(?P<number>\d{3})$")
_LEGACY_FA_GL_PATTERN = re.compile(r"^FA-GL-\d+$")


def canonical_procedure_id(value: str) -> str:
    """Return a canonical compact audit-procedure identifier.

    Procedure identifiers consist of a domain or procedure-family prefix
    followed by a three-digit number.

    Examples:

    ``GL003``
    ``PAY001``
    ``PROC012``
    ``ITGC004``

    The corresponding display forms containing one separator before the
    numeric component are also accepted.

    Legacy ``FA-GL`` methodology references are deliberately rejected because
    their numbering must not be assumed to match the engine catalogue.
    """

    cleaned = value.strip().upper()

    if _LEGACY_FA_GL_PATTERN.fullmatch(cleaned):
        raise ValueError(
            "Legacy FA-GL methodology references must be reconciled "
            "explicitly with the engine procedure catalogue and cannot "
            "be converted automatically."
        )

    canonical_match = _CANONICAL_PATTERN.fullmatch(cleaned)

    if canonical_match is not None:
        return cleaned

    display_match = _DISPLAY_PATTERN.fullmatch(cleaned)

    if display_match is not None:
        return f"{display_match.group('prefix')}{display_match.group('number')}"

    raise ValueError(
        "Procedure identifier must contain a 2-to-12 letter prefix "
        "followed by a three-digit number, for example 'GL003', "
        "'PAY001' or 'ITGC004'. The display form may contain one "
        "hyphen before the number, for example 'GL-003'."
    )


def procedure_display_id(value: str) -> str:
    """Return the user-facing display form of a procedure identifier."""

    canonical = canonical_procedure_id(value)

    match = _CANONICAL_PATTERN.fullmatch(canonical)

    if match is None:
        raise ValueError("Could not format the procedure identifier.")

    return f"{match.group('prefix')}-{match.group('number')}"
