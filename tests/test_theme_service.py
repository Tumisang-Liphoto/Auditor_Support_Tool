"""Tests for application theme resolution and stylesheets."""

import pytest
from PySide6.QtCore import Qt

from auditor_support_tool.services.theme_service import (
    build_stylesheet,
    resolve_effective_mode,
)


def test_system_dark_resolves_to_dark() -> None:
    assert (
        resolve_effective_mode(
            "system",
            Qt.ColorScheme.Dark,
        )
        == "dark"
    )


def test_system_light_resolves_to_light() -> None:
    assert (
        resolve_effective_mode(
            "system",
            Qt.ColorScheme.Light,
        )
        == "light"
    )


def test_explicit_dark_overrides_system_light() -> None:
    assert (
        resolve_effective_mode(
            "dark",
            Qt.ColorScheme.Light,
        )
        == "dark"
    )


def test_dark_stylesheet_contains_dark_palette() -> None:
    stylesheet = build_stylesheet(
        theme="mint_green",
        mode="dark",
    )

    assert "#171C18" in stylesheet
    assert "#81D185" in stylesheet


def test_invalid_effective_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_stylesheet(
            theme="mint_green",
            mode="automatic",
        )
