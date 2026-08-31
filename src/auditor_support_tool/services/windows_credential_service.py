"""Secure per-user secret storage using Windows Credential Manager."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from typing import Protocol

_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


class CredentialStoreError(RuntimeError):
    """Raised when a secure credential-store operation fails."""


class CredentialStore(Protocol):
    """Minimal secret-store contract used by application integrations."""

    def get_secret(self, target: str) -> str | None:
        """Return a stored secret or ``None`` when absent."""

    def set_secret(
        self,
        target: str,
        secret: str,
    ) -> None:
        """Persist one secret."""

    def delete_secret(self, target: str) -> None:
        """Remove one secret when present."""


@dataclass(frozen=True, slots=True)
class _CredentialApi:
    cred_write: object
    cred_read: object
    cred_delete: object
    cred_free: object


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialService:
    """Store integration secrets in the current user's Windows vault."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows Credential Manager is available only on Windows.")

        advapi32 = ctypes.WinDLL(
            "Advapi32.dll",
            use_last_error=True,
        )

        cred_write = advapi32.CredWriteW
        cred_write.argtypes = [
            ctypes.POINTER(_CREDENTIALW),
            wintypes.DWORD,
        ]
        cred_write.restype = wintypes.BOOL

        cred_read = advapi32.CredReadW
        cred_read.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
        ]
        cred_read.restype = wintypes.BOOL

        cred_delete = advapi32.CredDeleteW
        cred_delete.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        cred_delete.restype = wintypes.BOOL

        cred_free = advapi32.CredFree
        cred_free.argtypes = [ctypes.c_void_p]
        cred_free.restype = None

        self._api = _CredentialApi(
            cred_write=cred_write,
            cred_read=cred_read,
            cred_delete=cred_delete,
            cred_free=cred_free,
        )

    def get_secret(
        self,
        target: str,
    ) -> str | None:
        """Return a UTF-8-safe secret from Windows Credential Manager."""

        cleaned_target = self._validate_target(target)

        pointer = ctypes.POINTER(_CREDENTIALW)()

        if not self._api.cred_read(
            cleaned_target,
            _CRED_TYPE_GENERIC,
            0,
            ctypes.byref(pointer),
        ):
            error_code = ctypes.get_last_error()

            if error_code == _ERROR_NOT_FOUND:
                return None

            raise CredentialStoreError(
                "Windows Credential Manager could not read "
                f"the requested credential (error {error_code})."
            )

        try:
            credential = pointer.contents
            blob_size = int(credential.CredentialBlobSize)

            if blob_size <= 0 or not credential.CredentialBlob:
                return ""

            raw = ctypes.string_at(
                credential.CredentialBlob,
                blob_size,
            )

            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise CredentialStoreError(
                    "The stored credential could not be decoded safely."
                ) from error
        finally:
            self._api.cred_free(pointer)

    def set_secret(
        self,
        target: str,
        secret: str,
    ) -> None:
        """Persist a secret in the current user's Windows vault."""

        cleaned_target = self._validate_target(target)

        if not isinstance(secret, str):
            raise TypeError("Credential secret must be text.")

        if not secret:
            raise ValueError("Credential secret cannot be blank.")

        blob = secret.encode("utf-8")
        blob_buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)

        credential = _CREDENTIALW()
        credential.Flags = 0
        credential.Type = _CRED_TYPE_GENERIC
        credential.TargetName = cleaned_target
        credential.Comment = "Auditor Support Tool secure integration credential"
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(
            blob_buffer,
            ctypes.POINTER(ctypes.c_ubyte),
        )
        credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
        credential.AttributeCount = 0
        credential.Attributes = None
        credential.TargetAlias = None
        credential.UserName = "OpenWebUI API Key"

        if not self._api.cred_write(
            ctypes.byref(credential),
            0,
        ):
            error_code = ctypes.get_last_error()

            raise CredentialStoreError(
                f"Windows Credential Manager could not save the credential (error {error_code})."
            )

    def delete_secret(
        self,
        target: str,
    ) -> None:
        """Delete one secret, treating an absent credential as success."""

        cleaned_target = self._validate_target(target)

        if self._api.cred_delete(
            cleaned_target,
            _CRED_TYPE_GENERIC,
            0,
        ):
            return

        error_code = ctypes.get_last_error()

        if error_code == _ERROR_NOT_FOUND:
            return

        raise CredentialStoreError(
            f"Windows Credential Manager could not delete the credential (error {error_code})."
        )

    @staticmethod
    def _validate_target(
        target: str,
    ) -> str:
        cleaned = target.strip()

        if not cleaned:
            raise ValueError("Credential target is required.")

        return cleaned
