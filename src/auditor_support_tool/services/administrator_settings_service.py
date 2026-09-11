"""Session-scoped administrator lock for protected application settings."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from auditor_support_tool.services.administrator_password_verifier import (
    ADMIN_PASSWORD_SALT_HEX,
    ADMIN_PASSWORD_VERIFIER_HEX,
)

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32


@dataclass(frozen=True, slots=True)
class AdministratorUnlockResult:
    """Outcome of one technician-password unlock attempt."""

    success: bool
    message: str


def derive_password_verifier(
    password: str,
    salt: bytes,
) -> bytes:
    """Derive the verifier stored in the application for one password."""

    if not password:
        raise ValueError("Technician password is required.")
    if not salt:
        raise ValueError("Technician-password salt is required.")

    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
    )


class AdministratorSettingsService(QObject):
    """Verify the shared technician password and hold only session unlock state."""

    lock_state_changed = Signal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        salt: bytes | None = None,
        verifier: bytes | None = None,
    ) -> None:
        super().__init__(parent)

        self._salt = self._configured_bytes(ADMIN_PASSWORD_SALT_HEX) if salt is None else salt
        self._verifier = (
            self._configured_bytes(ADMIN_PASSWORD_VERIFIER_HEX) if verifier is None else verifier
        )
        self._unlocked = False

    @property
    def is_configured(self) -> bool:
        """Return whether this build contains a technician-password verifier."""

        return bool(self._salt and self._verifier)

    @property
    def is_unlocked(self) -> bool:
        """Return whether protected settings are unlocked for this app session."""

        return self._unlocked

    def verify_password(
        self,
        password: str,
    ) -> bool:
        """Return whether ``password`` matches the embedded verifier."""

        if not self.is_configured or not password:
            return False

        candidate = derive_password_verifier(password, self._salt)
        return hmac.compare_digest(candidate, self._verifier)

    def unlock(
        self,
        password: str,
    ) -> AdministratorUnlockResult:
        """Unlock protected settings for this application session."""

        if not self.is_configured:
            return AdministratorUnlockResult(
                success=False,
                message=(
                    "The technician password is not configured for this application build. "
                    "ICT must configure it before protected settings can be changed."
                ),
            )

        if not self.verify_password(password):
            return AdministratorUnlockResult(
                success=False,
                message="The technician password is incorrect.",
            )

        if not self._unlocked:
            self._unlocked = True
            self.lock_state_changed.emit(True)

        return AdministratorUnlockResult(
            success=True,
            message="Administrator settings unlocked for this application session.",
        )

    def lock(self) -> None:
        """Lock protected settings immediately."""

        if not self._unlocked:
            return

        self._unlocked = False
        self.lock_state_changed.emit(False)

    @staticmethod
    def _configured_bytes(value: str) -> bytes:
        cleaned = value.strip()
        if not cleaned:
            return b""

        try:
            return bytes.fromhex(cleaned)
        except ValueError:
            return b""
