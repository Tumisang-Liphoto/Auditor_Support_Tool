"""Tests for application theme resolution and stylesheets."""

import pytest
from PySide6.QtCore import Qt

from auditor_support_tool.services.theme_service import (
    THEME_DEFINITIONS,
    build_stylesheet,
    get_theme_definition,
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


@pytest.mark.parametrize(
    "theme_key",
    tuple(THEME_DEFINITIONS),
)
def test_each_theme_builds_light_stylesheet(
    theme_key: str,
) -> None:
    definition = get_theme_definition(theme_key)

    stylesheet = build_stylesheet(
        theme=theme_key,
        mode="light",
    )

    assert definition["accent"] in stylesheet
    assert definition["sidebar_light"] in stylesheet


@pytest.mark.parametrize(
    "theme_key",
    tuple(THEME_DEFINITIONS),
)
def test_each_theme_builds_dark_stylesheet(
    theme_key: str,
) -> None:
    definition = get_theme_definition(theme_key)

    stylesheet = build_stylesheet(
        theme=theme_key,
        mode="dark",
    )

    assert definition["accent"] in stylesheet
    assert definition["sidebar_dark"] in stylesheet


def test_invalid_theme_is_rejected() -> None:
    with pytest.raises(ValueError):
        get_theme_definition("unsupported_theme")


def test_invalid_effective_mode_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_stylesheet(
            theme="mint_green",
            mode="automatic",
        )
