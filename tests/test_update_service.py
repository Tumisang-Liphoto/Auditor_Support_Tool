"""Tests for GitHub release update checking."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from auditor_support_tool.core.constants import (
    APP_EXECUTABLE_NAME,
    UPDATE_CHECKSUM_ASSET_NAME,
    UPDATE_MANIFEST_NAME,
    UPDATE_PACKAGE_ASSET_NAME,
    UPDATER_EXECUTABLE_NAME,
)
from auditor_support_tool.core.paths import ApplicationPaths
from auditor_support_tool.services.update_service import (
    UpdateService,
    UpdateServiceError,
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


def _application_paths(tmp_path: Path) -> ApplicationPaths:
    """Create isolated application paths for updater preparation tests."""
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    updates = cache / "Updates"

    paths = ApplicationPaths(
        data=data,
        config=tmp_path / "config",
        cache=cache,
        logs=tmp_path / "logs",
        workspaces=data / "Workspaces",
        workspace_backups=data / "Backups" / "Workspaces",
        workspace_recovery=data / "Recovery",
        backups=data / "Backups" / "Application",
        updates=updates,
        update_downloads=updates / "Downloads",
        update_staging=updates / "Staging",
        update_runtime=updates / "Runtime",
        temporary=cache / "Temporary",
    )

    paths.update_runtime.mkdir(parents=True)
    paths.backups.mkdir(parents=True)

    return paths


def _local_update_assets(
    tmp_path: Path,
    *,
    version: str = "0.2.0",
) -> tuple[Path, Path]:
    """Create a valid local update ZIP and matching checksum file."""
    package = tmp_path / UPDATE_PACKAGE_ASSET_NAME

    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            APP_EXECUTABLE_NAME,
            b"new application",
        )
        archive.writestr(
            UPDATER_EXECUTABLE_NAME,
            b"new updater",
        )
        archive.writestr(
            UPDATE_MANIFEST_NAME,
            json.dumps(
                {
                    "version": version,
                    "application_executable": APP_EXECUTABLE_NAME,
                }
            ),
        )

    checksum = tmp_path / UPDATE_CHECKSUM_ASSET_NAME
    checksum.write_text(
        f"{hashlib.sha256(package.read_bytes()).hexdigest()}  "
        f"{UPDATE_PACKAGE_ASSET_NAME}\n",
        encoding="utf-8",
    )

    return package, checksum


def _update_result(
    monkeypatch,
    service: UpdateService,
    package: Path,
    checksum: Path,
):
    """Return an available release backed by the supplied local assets."""
    release = make_release(
        "v0.2.0",
        assets=[
            {
                "name": UPDATE_PACKAGE_ASSET_NAME,
                "browser_download_url": "https://example.invalid/application.zip",
                "size": package.stat().st_size,
                "content_type": "application/zip",
            },
            {
                "name": UPDATE_CHECKSUM_ASSET_NAME,
                "browser_download_url": "https://example.invalid/application.sha256",
                "size": checksum.stat().st_size,
                "content_type": "text/plain",
            },
        ],
    )

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: release,
    )

    return service.check_for_updates("stable")


def test_prepare_update_verifies_extracts_and_builds_runtime_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A valid update should be verified, extracted and prepared locally."""
    paths = _application_paths(tmp_path)

    service = UpdateService(
        current_version="0.1.0",
        paths=paths,
    )

    package, checksum = _local_update_assets(tmp_path)
    result = _update_result(
        monkeypatch,
        service,
        package,
        checksum,
    )

    source_assets = {
        UPDATE_PACKAGE_ASSET_NAME: package,
        UPDATE_CHECKSUM_ASSET_NAME: checksum,
    }

    progress = []

    def download(
        asset,
        destination,
        progress_callback,
    ):
        payload = source_assets[asset.name].read_bytes()
        destination.write_bytes(payload)

        if progress_callback is not None:
            progress_callback(
                len(payload),
                len(payload),
            )

    installation = tmp_path / "installed"
    installation.mkdir()

    monkeypatch.setattr(
        service,
        "_download_asset",
        download,
    )
    monkeypatch.setattr(
        service,
        "_installation_directory",
        lambda: installation,
    )

    prepared = service.prepare_update(
        result,
        progress_callback=lambda current, total: progress.append(
            (current, total)
        ),
    )

    assert str(prepared.version) == "0.2.0"
    assert prepared.installation_directory == installation
    assert prepared.application_executable == installation / APP_EXECUTABLE_NAME
    assert prepared.backup_root == paths.backups

    assert prepared.staging_directory == paths.update_staging / "0.2.0"

    assert (
        prepared.staging_directory / APP_EXECUTABLE_NAME
    ).read_bytes() == b"new application"

    assert (
        prepared.staging_directory / UPDATER_EXECUTABLE_NAME
    ).read_bytes() == b"new updater"

    assert prepared.updater_copy.parent == paths.update_runtime
    assert prepared.updater_copy.read_bytes() == b"new updater"

    assert prepared.health_marker.parent == paths.update_runtime
    assert prepared.health_marker.exists() is False
    assert prepared.token

    assert progress == [
        (
            package.stat().st_size,
            package.stat().st_size,
        )
    ]


def test_prepare_update_rejects_checksum_mismatch_before_extraction(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """A bad SHA-256 must stop preparation before the package is extracted."""
    paths = _application_paths(tmp_path)

    service = UpdateService(
        current_version="0.1.0",
        paths=paths,
    )

    package, checksum = _local_update_assets(tmp_path)

    checksum.write_text(
        f"{'0' * 64}  {UPDATE_PACKAGE_ASSET_NAME}\n",
        encoding="utf-8",
    )

    result = _update_result(
        monkeypatch,
        service,
        package,
        checksum,
    )

    source_assets = {
        UPDATE_PACKAGE_ASSET_NAME: package,
        UPDATE_CHECKSUM_ASSET_NAME: checksum,
    }

    def download(
        asset,
        destination,
        _progress_callback,
    ):
        destination.write_bytes(
            source_assets[asset.name].read_bytes()
        )

    def unexpected_extract(*_args):
        pytest.fail(
            "checksum mismatch must be rejected before extraction"
        )

    monkeypatch.setattr(
        service,
        "_download_asset",
        download,
    )
    monkeypatch.setattr(
        service,
        "_safe_extract",
        unexpected_extract,
    )

    with pytest.raises(
        UpdateServiceError,
        match="SHA-256 verification",
    ):
        service.prepare_update(result)


@pytest.mark.parametrize(
    "missing_asset",
    [
        UPDATE_PACKAGE_ASSET_NAME,
        UPDATE_CHECKSUM_ASSET_NAME,
    ],
)

def test_prepare_update_rejects_missing_required_asset(
    monkeypatch,
    tmp_path: Path,
    missing_asset: str,
) -> None:
    """Preparation must fail before download when a required asset is absent."""
    paths = _application_paths(tmp_path)

    service = UpdateService(
        current_version="0.1.0",
        paths=paths,
    )

    package, checksum = _local_update_assets(tmp_path)

    assets = [
        {
            "name": UPDATE_PACKAGE_ASSET_NAME,
            "browser_download_url": "https://example.invalid/application.zip",
            "size": package.stat().st_size,
            "content_type": "application/zip",
        },
        {
            "name": UPDATE_CHECKSUM_ASSET_NAME,
            "browser_download_url": "https://example.invalid/application.sha256",
            "size": checksum.stat().st_size,
            "content_type": "text/plain",
        },
    ]

    assets = [
        asset
        for asset in assets
        if asset["name"] != missing_asset
    ]

    release = make_release(
        "v0.2.0",
        assets=assets,
    )

    monkeypatch.setattr(
        service,
        "_request_json",
        lambda _url: release,
    )

    result = service.check_for_updates("stable")

    monkeypatch.setattr(
        service,
        "_download_asset",
        lambda *_args: pytest.fail(
            "missing asset must fail before download"
        ),
    )

    with pytest.raises(
        UpdateServiceError,
        match="release is missing",
    ):
        service.prepare_update(result)
