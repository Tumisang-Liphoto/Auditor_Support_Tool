"""Tests for GitHub release update checking."""

import pytest

from auditor_support_tool.services.update_service import (
    UpdateService,
    UpdateStatus,
)


def make_release(
    tag_name: str,
    *,
    prerelease: bool = False,
    draft: bool = False,
    assets: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Create a representative GitHub release response."""

    return {
        "tag_name": tag_name,
        "name": f"Release {tag_name}",
        "body": f"Release notes for {tag_name}",
        "html_url": (f"https://github.com/example/project/releases/tag/{tag_name}"),
        "published_at": "2026-07-31T08:00:00Z",
        "prerelease": prerelease,
        "draft": draft,
        "assets": assets or [],
    }


def test_stable_update_is_detected(
    monkeypatch,
) -> None:
    service = UpdateService(current_version="0.1.0")

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: make_release("v0.2.0"),
    )

    result = service.check_for_updates("stable")

    assert result.status == UpdateStatus.AVAILABLE
    assert result.update_available is True
    assert result.release is not None
    assert str(result.release.version) == "0.2.0"


def test_current_version_is_reported(
    monkeypatch,
) -> None:
    service = UpdateService(current_version="0.2.0")

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: make_release("v0.2.0"),
    )

    result = service.check_for_updates("stable")

    assert result.status == UpdateStatus.CURRENT
    assert result.update_available is False


def test_testing_channel_includes_prereleases(
    monkeypatch,
) -> None:
    service = UpdateService(current_version="0.1.0")

    releases = [
        make_release("v0.1.1"),
        make_release(
            "v0.2.0-beta.1",
            prerelease=True,
        ),
    ]

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: releases,
    )

    result = service.check_for_updates("testing")

    assert result.status == UpdateStatus.AVAILABLE
    assert result.release is not None
    assert str(result.release.version) == "0.2.0b1"
    assert result.release.prerelease is True


def test_testing_channel_ignores_drafts(
    monkeypatch,
) -> None:
    service = UpdateService(current_version="0.1.0")

    releases = [
        make_release(
            "v9.0.0",
            draft=True,
        ),
        make_release("v0.1.1"),
    ]

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: releases,
    )

    result = service.check_for_updates("testing")

    assert result.release is not None
    assert str(result.release.version) == "0.1.1"


def test_release_assets_are_parsed(
    monkeypatch,
) -> None:
    service = UpdateService(current_version="0.1.0")

    release = make_release(
        "v0.2.0",
        assets=[
            {
                "name": ("Auditor-Support-Tool-Windows-x64.zip"),
                "browser_download_url": ("https://example.org/application.zip"),
                "size": 1024,
                "content_type": "application/zip",
                "digest": "sha256:abc123",
            },
            {
                "name": ("Auditor-Support-Tool-Windows-x64.zip.sha256"),
                "browser_download_url": ("https://example.org/application.sha256"),
                "size": 64,
                "content_type": "text/plain",
            },
        ],
    )

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: release,
    )

    result = service.check_for_updates("stable")

    assert result.package_asset is not None
    assert result.package_asset.size == 1024
    assert result.package_asset.digest == "sha256:abc123"
    assert result.checksum_asset is not None


def test_no_testing_releases_are_reported(
    monkeypatch,
) -> None:
    service = UpdateService(current_version="0.1.0")

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: [],
    )

    result = service.check_for_updates("testing")

    assert result.status == UpdateStatus.NO_RELEASES
    assert result.release is None


def test_invalid_channel_is_rejected() -> None:
    service = UpdateService(current_version="0.1.0")

    with pytest.raises(ValueError):
        service.check_for_updates("experimental")
