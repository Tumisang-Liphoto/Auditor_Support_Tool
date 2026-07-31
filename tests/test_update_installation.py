"""Tests for secure update staging helpers."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from packaging.version import Version

from auditor_support_tool.core.constants import (
    APP_EXECUTABLE_NAME,
    UPDATE_MANIFEST_NAME,
    UPDATER_EXECUTABLE_NAME,
)
from auditor_support_tool.services.update_service import (
    UpdateService,
    UpdateServiceError,
)


def test_sha256_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.bin"
    source.write_bytes(b"auditor-support-tool")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    assert UpdateService._sha256_file(source) == expected


def test_safe_extract_rejects_parent_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", "unsafe")

    with pytest.raises(UpdateServiceError):
        UpdateService._safe_extract(archive, tmp_path / "staging")


def test_validate_staging_accepts_complete_package(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / APP_EXECUTABLE_NAME).write_bytes(b"application")
    (staging / UPDATER_EXECUTABLE_NAME).write_bytes(b"updater")
    (staging / UPDATE_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "application_executable": APP_EXECUTABLE_NAME,
            }
        ),
        encoding="utf-8",
    )

    UpdateService._validate_staging(staging, Version("0.2.0"))


def test_validate_staging_rejects_wrong_version(tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / APP_EXECUTABLE_NAME).write_bytes(b"application")
    (staging / UPDATER_EXECUTABLE_NAME).write_bytes(b"updater")
    (staging / UPDATE_MANIFEST_NAME).write_text(
        json.dumps(
            {
                "version": "0.3.0",
                "application_executable": APP_EXECUTABLE_NAME,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(UpdateServiceError):
        UpdateService._validate_staging(staging, Version("0.2.0"))
