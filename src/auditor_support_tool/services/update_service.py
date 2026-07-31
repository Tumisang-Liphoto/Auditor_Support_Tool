"""GitHub release discovery, download and update preparation."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

from auditor_support_tool.core.constants import (
    APP_EXECUTABLE_NAME,
    GITHUB_API_VERSION,
    GITHUB_REPOSITORY_NAME,
    GITHUB_REPOSITORY_OWNER,
    UPDATE_CHECKSUM_ASSET_NAME,
    UPDATE_MANIFEST_NAME,
    UPDATE_PACKAGE_ASSET_NAME,
    UPDATE_REQUEST_TIMEOUT_SECONDS,
    UPDATER_EXECUTABLE_NAME,
)
from auditor_support_tool.core.paths import ApplicationPaths

ProgressCallback = Callable[[int, int], None]


class UpdateStatus(StrEnum):
    """Possible outcomes of an update check."""

    AVAILABLE = "available"
    CURRENT = "current"
    NO_RELEASES = "no_releases"
    ERROR = "error"


class UpdateServiceError(RuntimeError):
    """Base error raised while processing an update."""


class NoPublishedReleaseError(UpdateServiceError):
    """Raised when the repository has no applicable release."""


@dataclass(frozen=True, slots=True)
class ReleaseAsset:
    """A downloadable file attached to a GitHub release."""

    name: str
    download_url: str
    size: int
    content_type: str = ""
    digest: str | None = None


@dataclass(frozen=True, slots=True)
class ReleaseInformation:
    """Relevant information about a published GitHub release."""

    tag_name: str
    version: Version
    name: str
    release_notes: str
    release_url: str
    published_at: str
    prerelease: bool
    draft: bool
    assets: tuple[ReleaseAsset, ...]

    def find_asset(self, asset_name: str) -> ReleaseAsset | None:
        for asset in self.assets:
            if asset.name == asset_name:
                return asset
        return None


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    """Result returned after checking GitHub for an update."""

    status: UpdateStatus
    current_version: Version
    channel: str
    message: str
    release: ReleaseInformation | None = None

    @property
    def update_available(self) -> bool:
        return self.status == UpdateStatus.AVAILABLE

    @property
    def package_asset(self) -> ReleaseAsset | None:
        if self.release is None:
            return None
        return self.release.find_asset(UPDATE_PACKAGE_ASSET_NAME)

    @property
    def checksum_asset(self) -> ReleaseAsset | None:
        if self.release is None:
            return None
        return self.release.find_asset(UPDATE_CHECKSUM_ASSET_NAME)


@dataclass(frozen=True, slots=True)
class PreparedUpdate:
    """A verified update ready for the external updater."""

    version: Version
    staging_directory: Path
    updater_copy: Path
    installation_directory: Path
    application_executable: Path
    backup_root: Path
    health_marker: Path
    token: str


class UpdateService:
    """Check GitHub Releases and prepare verified application updates."""

    def __init__(
        self,
        current_version: str,
        *,
        paths: ApplicationPaths | None = None,
        owner: str = GITHUB_REPOSITORY_OWNER,
        repository: str = GITHUB_REPOSITORY_NAME,
        timeout_seconds: int = UPDATE_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._current_version = Version(current_version)
        self._paths = paths
        self._owner = owner
        self._repository = repository
        self._timeout_seconds = timeout_seconds
        self._releases_url = f"https://api.github.com/repos/{owner}/{repository}/releases"

    def check_for_updates(self, channel: str) -> UpdateCheckResult:
        """Check the selected Stable or Testing channel."""

        normalized_channel = channel.strip().lower()
        if normalized_channel not in {"stable", "testing"}:
            raise ValueError("Update channel must be 'stable' or 'testing'.")

        try:
            release = (
                self._fetch_stable_release()
                if normalized_channel == "stable"
                else self._fetch_testing_release()
            )
        except NoPublishedReleaseError:
            return UpdateCheckResult(
                status=UpdateStatus.NO_RELEASES,
                current_version=self._current_version,
                channel=normalized_channel,
                message=("No published GitHub release is available for the selected channel."),
            )
        except UpdateServiceError as error:
            return UpdateCheckResult(
                status=UpdateStatus.ERROR,
                current_version=self._current_version,
                channel=normalized_channel,
                message=str(error),
            )

        if release.version > self._current_version:
            status = UpdateStatus.AVAILABLE
            message = (
                f"Version {release.version} is available on the "
                f"{normalized_channel.title()} channel."
            )
        else:
            status = UpdateStatus.CURRENT
            message = (
                "You are using the latest version available on the "
                f"{normalized_channel.title()} channel."
            )

        return UpdateCheckResult(
            status=status,
            current_version=self._current_version,
            channel=normalized_channel,
            message=message,
            release=release,
        )

    def prepare_update(
        self,
        result: UpdateCheckResult,
        progress_callback: ProgressCallback | None = None,
    ) -> PreparedUpdate:
        """Download, verify and safely extract an available release."""

        if self._paths is None:
            raise UpdateServiceError("Application update paths were not configured.")
        if not result.update_available or result.release is None:
            raise UpdateServiceError("No newer release is available to install.")

        package_asset = result.package_asset
        checksum_asset = result.checksum_asset
        if package_asset is None:
            raise UpdateServiceError(f"The release is missing {UPDATE_PACKAGE_ASSET_NAME}.")
        if checksum_asset is None:
            raise UpdateServiceError(f"The release is missing {UPDATE_CHECKSUM_ASSET_NAME}.")

        release_id = str(result.release.version)
        download_directory = self._paths.update_downloads / release_id
        staging_directory = self._paths.update_staging / release_id
        shutil.rmtree(download_directory, ignore_errors=True)
        shutil.rmtree(staging_directory, ignore_errors=True)
        download_directory.mkdir(parents=True, exist_ok=True)
        staging_directory.mkdir(parents=True, exist_ok=True)

        package_path = download_directory / UPDATE_PACKAGE_ASSET_NAME
        checksum_path = download_directory / UPDATE_CHECKSUM_ASSET_NAME
        self._download_asset(package_asset, package_path, progress_callback)
        self._download_asset(checksum_asset, checksum_path, None)

        expected_hash = self._read_expected_hash(checksum_path)
        actual_hash = self._sha256_file(package_path)
        if actual_hash.lower() != expected_hash.lower():
            raise UpdateServiceError(
                "The downloaded update failed SHA-256 verification and was rejected."
            )

        self._safe_extract(package_path, staging_directory)
        self._validate_staging(staging_directory, result.release.version)

        installation_directory = self._installation_directory()
        updater_source = staging_directory / UPDATER_EXECUTABLE_NAME
        updater_copy = self._paths.update_runtime / (
            f"updater-{result.release.version}-{uuid.uuid4().hex}.exe"
        )
        shutil.copy2(updater_source, updater_copy)

        token = uuid.uuid4().hex
        health_marker = self._paths.update_runtime / f"health-{token}.ok"
        health_marker.unlink(missing_ok=True)

        return PreparedUpdate(
            version=result.release.version,
            staging_directory=staging_directory,
            updater_copy=updater_copy,
            installation_directory=installation_directory,
            application_executable=installation_directory / APP_EXECUTABLE_NAME,
            backup_root=self._paths.backups,
            health_marker=health_marker,
            token=token,
        )

    def launch_prepared_update(self, prepared: PreparedUpdate) -> None:
        """Start the external updater and return immediately."""

        command = [
            str(prepared.updater_copy),
            "--wait-pid",
            str(os.getpid()),
            "--source",
            str(prepared.staging_directory),
            "--target",
            str(prepared.installation_directory),
            "--backup-root",
            str(prepared.backup_root),
            "--app-exe",
            APP_EXECUTABLE_NAME,
            "--health-marker",
            str(prepared.health_marker),
            "--health-token",
            prepared.token,
            "--version",
            str(prepared.version),
        ]
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(
            command,
            close_fds=True,
            creationflags=creationflags,
        )

    def _fetch_stable_release(self) -> ReleaseInformation:
        payload = self._request_json(f"{self._releases_url}/latest")
        if not isinstance(payload, dict):
            raise UpdateServiceError("GitHub returned an unexpected release response.")
        try:
            return self._parse_release(payload)
        except InvalidVersion as error:
            raise UpdateServiceError(
                "The latest GitHub release has an invalid version tag."
            ) from error

    def _fetch_testing_release(self) -> ReleaseInformation:
        payload = self._request_json(f"{self._releases_url}?per_page=30")
        if not isinstance(payload, list):
            raise UpdateServiceError("GitHub returned an unexpected releases response.")

        candidates: list[ReleaseInformation] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                release = self._parse_release(item)
            except InvalidVersion:
                continue
            if not release.draft:
                candidates.append(release)

        if not candidates:
            raise NoPublishedReleaseError("No published GitHub release was found.")
        return max(candidates, key=lambda release: release.version)

    def _parse_release(self, payload: dict[object, object]) -> ReleaseInformation:
        tag_name = str(payload.get("tag_name") or "").strip()
        if not tag_name:
            raise InvalidVersion("Missing release tag")
        version_text = tag_name[1:] if tag_name[:1].lower() == "v" else tag_name
        version = Version(version_text)

        assets: list[ReleaseAsset] = []
        raw_assets = payload.get("assets")
        if isinstance(raw_assets, list):
            for raw_asset in raw_assets:
                if not isinstance(raw_asset, dict):
                    continue
                name = str(raw_asset.get("name") or "").strip()
                url = str(raw_asset.get("browser_download_url") or "").strip()
                if not name or not url:
                    continue
                try:
                    size = int(raw_asset.get("size", 0))
                except TypeError, ValueError:
                    size = 0
                digest_value = raw_asset.get("digest")
                assets.append(
                    ReleaseAsset(
                        name=name,
                        download_url=url,
                        size=size,
                        content_type=str(raw_asset.get("content_type") or ""),
                        digest=str(digest_value).strip() if digest_value else None,
                    )
                )

        return ReleaseInformation(
            tag_name=tag_name,
            version=version,
            name=str(payload.get("name") or tag_name),
            release_notes=str(payload.get("body") or ""),
            release_url=str(payload.get("html_url") or ""),
            published_at=str(payload.get("published_at") or ""),
            prerelease=bool(payload.get("prerelease", False)),
            draft=bool(payload.get("draft", False)),
            assets=tuple(assets),
        )

    def _request_json(self, url: str) -> object:
        request = self._request(url)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                data = response.read()
        except HTTPError as error:
            if error.code == 404:
                raise NoPublishedReleaseError("No published release was found.") from error
            if error.code in {403, 429}:
                raise UpdateServiceError(
                    "GitHub temporarily refused the request or its API limit was reached."
                ) from error
            raise UpdateServiceError(
                f"GitHub returned HTTP {error.code} while checking for updates."
            ) from error
        except (URLError, TimeoutError) as error:
            raise UpdateServiceError(
                "The application could not connect to GitHub. Check the internet connection."
            ) from error

        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpdateServiceError("GitHub returned an unreadable update response.") from error

    def _download_asset(
        self,
        asset: ReleaseAsset,
        destination: Path,
        progress_callback: ProgressCallback | None,
    ) -> None:
        request = self._request(asset.download_url)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                total = int(response.headers.get("Content-Length") or asset.size or 0)
                downloaded = 0
                with destination.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        output.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total)
        except (HTTPError, URLError, TimeoutError) as error:
            destination.unlink(missing_ok=True)
            raise UpdateServiceError(
                f"The update asset {asset.name} could not be downloaded."
            ) from error

    def _request(self, url: str) -> Request:
        return Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": f"Auditor-Support-Tool/{self._current_version}",
            },
        )

    @staticmethod
    def _read_expected_hash(checksum_path: Path) -> str:
        content = checksum_path.read_text(encoding="utf-8").strip()
        first_token = content.split()[0] if content else ""
        if len(first_token) != 64 or any(c not in "0123456789abcdefABCDEF" for c in first_token):
            raise UpdateServiceError("The release checksum file is invalid.")
        return first_token

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_extract(archive_path: Path, destination: Path) -> None:
        destination_root = destination.resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                member_path = (destination / member.filename).resolve()
                try:
                    member_path.relative_to(destination_root)
                except ValueError as error:
                    raise UpdateServiceError(
                        "The update archive contains an unsafe path."
                    ) from error
                if member.is_dir():
                    member_path.mkdir(parents=True, exist_ok=True)
                else:
                    member_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, member_path.open("wb") as output:
                        shutil.copyfileobj(source, output)

    @staticmethod
    def _validate_staging(staging_directory: Path, expected_version: Version) -> None:
        manifest_path = staging_directory / UPDATE_MANIFEST_NAME
        app_path = staging_directory / APP_EXECUTABLE_NAME
        updater_path = staging_directory / UPDATER_EXECUTABLE_NAME
        if not manifest_path.is_file() or not app_path.is_file() or not updater_path.is_file():
            raise UpdateServiceError(
                "The update package is incomplete or has an unexpected layout."
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise UpdateServiceError("The update manifest is unreadable.") from error
        if str(manifest.get("version", "")) != str(expected_version):
            raise UpdateServiceError(
                "The update manifest version does not match the GitHub release."
            )
        if manifest.get("application_executable") != APP_EXECUTABLE_NAME:
            raise UpdateServiceError("The update manifest names an unexpected executable.")

    @staticmethod
    def _installation_directory() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        raise UpdateServiceError(
            "Installation can only be started from the packaged Windows application."
        )
