"""Cryptographic integrity checks for audit source files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

_HASH_CHUNK_SIZE = 1024 * 1024


class SourceIntegrityStatus(StrEnum):
    """Outcome of comparing a source file with its saved SHA-256 hash."""

    VERIFIED = "verified"
    MISMATCH = "mismatch"
    UNVERIFIED = "unverified"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class SourceIntegrityResult:
    """Result of one source-file integrity verification."""

    status: SourceIntegrityStatus
    source_path: Path
    expected_sha256: str | None
    actual_sha256: str | None

    @property
    def is_verified(self) -> bool:
        """Return whether the file exactly matches its saved hash."""

        return self.status == SourceIntegrityStatus.VERIFIED


class SourceIntegrityService:
    """Calculate and verify SHA-256 hashes for audit source files."""

    def sha256_file(
        self,
        file_path: str | Path,
    ) -> str:
        """Return the lowercase SHA-256 digest for a file."""

        path = Path(file_path).expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        digest = sha256()

        with path.open("rb") as source_file:
            while chunk := source_file.read(_HASH_CHUNK_SIZE):
                digest.update(chunk)

        return digest.hexdigest()

    def verify(
        self,
        file_path: str | Path,
        expected_sha256: str | None,
    ) -> SourceIntegrityResult:
        """Compare a source file with an expected SHA-256 digest."""

        path = Path(file_path).expanduser().resolve()

        if not path.is_file():
            return SourceIntegrityResult(
                status=SourceIntegrityStatus.MISSING,
                source_path=path,
                expected_sha256=self._normalise_optional_hash(expected_sha256),
                actual_sha256=None,
            )

        actual_hash = self.sha256_file(path)
        expected_hash = self._normalise_optional_hash(expected_sha256)

        if expected_hash is None:
            return SourceIntegrityResult(
                status=SourceIntegrityStatus.UNVERIFIED,
                source_path=path,
                expected_sha256=None,
                actual_sha256=actual_hash,
            )

        status = (
            SourceIntegrityStatus.VERIFIED
            if actual_hash == expected_hash
            else SourceIntegrityStatus.MISMATCH
        )

        return SourceIntegrityResult(
            status=status,
            source_path=path,
            expected_sha256=expected_hash,
            actual_sha256=actual_hash,
        )

    @staticmethod
    def _normalise_optional_hash(
        value: str | None,
    ) -> str | None:
        """Validate and normalise an optional SHA-256 digest."""

        if value is None:
            return None

        cleaned = value.strip().lower()

        if not cleaned:
            return None

        if len(cleaned) != 64 or any(character not in "0123456789abcdef" for character in cleaned):
            raise ValueError("Saved source SHA-256 hash is invalid.")

        return cleaned
