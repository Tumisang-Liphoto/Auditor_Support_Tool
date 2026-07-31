"""GitHub release discovery for application updates."""

import json
from dataclasses import dataclass
from enum import StrEnum
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

from auditor_support_tool.core.constants import (
    GITHUB_API_VERSION,
    GITHUB_REPOSITORY_NAME,
    GITHUB_REPOSITORY_OWNER,
    UPDATE_CHECKSUM_ASSET_NAME,
    UPDATE_PACKAGE_ASSET_NAME,
    UPDATE_REQUEST_TIMEOUT_SECONDS,
)


class UpdateStatus(StrEnum):
    """Possible outcomes of an update check."""

    AVAILABLE = "available"
    CURRENT = "current"
    NO_RELEASES = "no_releases"
    ERROR = "error"


class UpdateServiceError(RuntimeError):
    """Base error raised while communicating with GitHub."""


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
        """Return a release asset with the specified name."""

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
        """Return whether a newer release was found."""

        return self.status == UpdateStatus.AVAILABLE

    @property
    def package_asset(self) -> ReleaseAsset | None:
        """Return the Windows update package, where available."""

        if self.release is None:
            return None

        return self.release.find_asset(UPDATE_PACKAGE_ASSET_NAME)

    @property
    def checksum_asset(self) -> ReleaseAsset | None:
        """Return the SHA-256 checksum file, where available."""

        if self.release is None:
            return None

        return self.release.find_asset(UPDATE_CHECKSUM_ASSET_NAME)


class UpdateService:
    """Check GitHub Releases for newer application versions."""

    def __init__(
        self,
        current_version: str,
        *,
        owner: str = GITHUB_REPOSITORY_OWNER,
        repository: str = GITHUB_REPOSITORY_NAME,
        timeout_seconds: int = UPDATE_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._current_version = Version(current_version)
        self._owner = owner
        self._repository = repository
        self._timeout_seconds = timeout_seconds

        self._releases_url = (
            f"https://api.github.com/repos/{self._owner}/{self._repository}/releases"
        )

    def check_for_updates(self, channel: str) -> UpdateCheckResult:
        """Check the selected Stable or Testing channel."""

        normalized_channel = channel.strip().lower()

        if normalized_channel not in {"stable", "testing"}:
            raise ValueError("Update channel must be 'stable' or 'testing'.")

        try:
            if normalized_channel == "stable":
                release = self._fetch_stable_release()
            else:
                release = self._fetch_testing_release()
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
                f"Version {release.version} is available "
                f"on the {normalized_channel.title()} channel."
            )
        else:
            status = UpdateStatus.CURRENT
            message = (
                "You are using the latest version available "
                f"on the {normalized_channel.title()} channel."
            )

        return UpdateCheckResult(
            status=status,
            current_version=self._current_version,
            channel=normalized_channel,
            message=message,
            release=release,
        )

    def _fetch_stable_release(self) -> ReleaseInformation:
        """Fetch the latest full, non-prerelease release."""

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
        """Fetch the newest version, including prereleases."""

        payload = self._request_json(f"{self._releases_url}?per_page=30")

        if not isinstance(payload, list):
            raise UpdateServiceError("GitHub returned an unexpected releases response.")

        candidates: list[ReleaseInformation] = []

        for release_payload in payload:
            if not isinstance(release_payload, dict):
                continue

            try:
                release = self._parse_release(release_payload)
            except InvalidVersion:
                continue

            if release.draft:
                continue

            candidates.append(release)

        if not candidates:
            raise NoPublishedReleaseError("No published GitHub release was found.")

        return max(candidates, key=lambda release: release.version)

    def _parse_release(
        self,
        payload: dict[object, object],
    ) -> ReleaseInformation:
        """Convert a GitHub release response into a model."""

        tag_name = str(payload.get("tag_name") or "").strip()

        if not tag_name:
            raise InvalidVersion("Missing release tag")

        version_text = tag_name[1:] if tag_name[:1].lower() == "v" else tag_name
        version = Version(version_text)

        raw_assets = payload.get("assets")
        assets: list[ReleaseAsset] = []

        if isinstance(raw_assets, list):
            for raw_asset in raw_assets:
                if not isinstance(raw_asset, dict):
                    continue

                asset_name = str(raw_asset.get("name") or "").strip()
                download_url = str(raw_asset.get("browser_download_url") or "").strip()

                if not asset_name or not download_url:
                    continue

                try:
                    size = int(raw_asset.get("size", 0))
                except TypeError, ValueError:
                    size = 0

                raw_digest = raw_asset.get("digest")
                digest = str(raw_digest).strip() if raw_digest else None

                assets.append(
                    ReleaseAsset(
                        name=asset_name,
                        download_url=download_url,
                        size=size,
                        content_type=str(raw_asset.get("content_type") or ""),
                        digest=digest,
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
        """Request and decode JSON from the GitHub REST API."""

        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": (f"Auditor-Support-Tool/{self._current_version}"),
            },
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                response_data = response.read()
        except HTTPError as error:
            if error.code == 404:
                raise NoPublishedReleaseError("No published release was found.") from error

            if error.code in {403, 429}:
                raise UpdateServiceError(
                    "GitHub temporarily refused the update request or its API limit was reached."
                ) from error

            raise UpdateServiceError(
                f"GitHub returned an error while checking for updates: HTTP {error.code}."
            ) from error
        except URLError as error:
            raise UpdateServiceError(
                "The application could not connect to GitHub. "
                "Check the internet connection and try again."
            ) from error
        except TimeoutError as error:
            raise UpdateServiceError("The GitHub update check timed out.") from error

        try:
            return json.loads(response_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpdateServiceError("GitHub returned an unreadable update response.") from error
