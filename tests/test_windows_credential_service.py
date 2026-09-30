"""Tests for secure Windows Credential Manager integration."""

import ctypes

import pytest

from auditor_support_tool.services import windows_credential_service as credential_module


class _FakeFunction:
    """Minimal callable stand-in for a ctypes Win32 function."""

    def __init__(self):
        self.argtypes = None
        self.restype = None

    def __call__(self, *_args):
        return True


class _FakeAdvapi32:
    """Fake Advapi32 library exposing the credential functions used by the service."""

    def __init__(self):
        self.CredWriteW = _FakeFunction()
        self.CredReadW = _FakeFunction()
        self.CredDeleteW = _FakeFunction()
        self.CredFree = _FakeFunction()


def test_constructor_binds_expected_windows_credential_functions(monkeypatch):
    """Construction should bind the expected Win32 credential functions."""
    fake_dll = _FakeAdvapi32()

    class _Windows:
        name = "nt"

    monkeypatch.setattr(credential_module, "os", _Windows())
    monkeypatch.setattr(
        credential_module.ctypes,
        "WinDLL",
        lambda name, *, use_last_error: fake_dll,
        raising=False,
    )

    service = credential_module.WindowsCredentialService()

    assert service._api.cred_write is fake_dll.CredWriteW
    assert service._api.cred_read is fake_dll.CredReadW
    assert service._api.cred_delete is fake_dll.CredDeleteW
    assert service._api.cred_free is fake_dll.CredFree
    assert fake_dll.CredWriteW.restype is credential_module.wintypes.BOOL
    assert fake_dll.CredReadW.restype is credential_module.wintypes.BOOL
    assert fake_dll.CredDeleteW.restype is credential_module.wintypes.BOOL
    assert fake_dll.CredFree.restype is None


def test_constructor_rejects_non_windows_platform(monkeypatch):
    """Credential Manager should fail explicitly outside Windows."""

    class _NonWindows:
        name = "posix"

    monkeypatch.setattr(credential_module, "os", _NonWindows())

    with pytest.raises(OSError, match="available only on Windows"):
        credential_module.WindowsCredentialService()


def _service(*, read=None, write=None, delete=None, free=None):
    """Create a service with an injected fake credential API."""
    service = credential_module.WindowsCredentialService.__new__(
        credential_module.WindowsCredentialService
    )
    service._api = credential_module._CredentialApi(
        cred_write=write or (lambda *_args: True),
        cred_read=read or (lambda *_args: False),
        cred_delete=delete or (lambda *_args: True),
        cred_free=free or (lambda *_args: None),
    )
    return service


def _read_api_for(raw: bytes, *, free_calls: list[object]):
    """Build fake read/free functions exposing the supplied raw credential bytes."""
    blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)

    credential = credential_module._CREDENTIALW()
    credential.CredentialBlobSize = len(raw)
    credential.CredentialBlob = ctypes.cast(
        blob,
        ctypes.POINTER(ctypes.c_ubyte),
    )

    credential_pointer = ctypes.pointer(credential)

    def read(_target, _cred_type, _flags, output_pointer):
        destination = ctypes.cast(
            output_pointer,
            ctypes.POINTER(ctypes.POINTER(credential_module._CREDENTIALW)),
        )
        destination[0] = credential_pointer
        return True

    def free(pointer):
        free_calls.append(pointer)

    return read, free


def test_validate_target_trims_whitespace():
    """Credential targets should be normalized before Win32 calls."""
    assert (
        credential_module.WindowsCredentialService._validate_target("  OpenWebUI  ")
        == "OpenWebUI"
    )


def test_validate_target_rejects_blank():
    """Blank Credential Manager targets should be rejected."""
    with pytest.raises(ValueError, match="Credential target is required"):
        credential_module.WindowsCredentialService._validate_target("   ")


def test_get_secret_returns_none_when_credential_is_absent(monkeypatch):
    """ERROR_NOT_FOUND should represent an absent credential, not a failure."""
    monkeypatch.setattr(
        credential_module.ctypes,
        "get_last_error",
        lambda: 1168,
        raising=False,
    )

    service = _service(read=lambda *_args: False)

    assert service.get_secret("target") is None


def test_get_secret_raises_for_windows_read_error(monkeypatch):
    """Unexpected Win32 read failures should surface as controlled errors."""
    monkeypatch.setattr(
        credential_module.ctypes,
        "get_last_error",
        lambda: 5,
        raising=False,
    )

    service = _service(read=lambda *_args: False)

    with pytest.raises(credential_module.CredentialStoreError, match=r"error 5"):
        service.get_secret("target")


def test_get_secret_decodes_utf8_and_frees_native_credential():
    """Stored UTF-8 secrets should be decoded and native memory released."""
    free_calls = []
    read, free = _read_api_for(
        "sëcret-🔐".encode(),
        free_calls=free_calls,
    )

    service = _service(read=read, free=free)

    assert service.get_secret(" target ") == "sëcret-🔐"
    assert len(free_calls) == 1


def test_get_secret_returns_empty_string_for_zero_length_blob():
    """A zero-length stored blob should be handled safely."""
    free_calls = []

    credential = credential_module._CREDENTIALW()
    credential.CredentialBlobSize = 0
    credential.CredentialBlob = ctypes.POINTER(ctypes.c_ubyte)()

    credential_pointer = ctypes.pointer(credential)

    def read(_target, _cred_type, _flags, output_pointer):
        destination = ctypes.cast(
            output_pointer,
            ctypes.POINTER(ctypes.POINTER(credential_module._CREDENTIALW)),
        )
        destination[0] = credential_pointer
        return True

    service = _service(
        read=read,
        free=lambda pointer: free_calls.append(pointer),
    )

    assert service.get_secret("target") == ""
    assert len(free_calls) == 1


def test_get_secret_returns_empty_string_for_missing_blob_pointer():
    """A missing native blob pointer should be handled safely."""
    free_calls = []

    credential = credential_module._CREDENTIALW()
    credential.CredentialBlobSize = 1
    credential.CredentialBlob = ctypes.POINTER(ctypes.c_ubyte)()

    credential_pointer = ctypes.pointer(credential)

    def read(_target, _cred_type, _flags, output_pointer):
        destination = ctypes.cast(
            output_pointer,
            ctypes.POINTER(ctypes.POINTER(credential_module._CREDENTIALW)),
        )
        destination[0] = credential_pointer
        return True

    service = _service(
        read=read,
        free=lambda pointer: free_calls.append(pointer),
    )

    assert service.get_secret("target") == ""
    assert len(free_calls) == 1


def test_get_secret_invalid_utf8_still_frees_native_credential():
    """Invalid stored bytes should fail safely without leaking native memory."""
    free_calls = []
    read, free = _read_api_for(
        b"\xff\xfe",
        free_calls=free_calls,
    )

    service = _service(read=read, free=free)

    with pytest.raises(
        credential_module.CredentialStoreError,
        match="could not be decoded safely",
    ):
        service.get_secret("target")

    assert len(free_calls) == 1


def test_set_secret_rejects_non_text_secret():
    """Binary objects should not be accepted as application secrets."""
    service = _service()

    with pytest.raises(TypeError, match="must be text"):
        service.set_secret("target", b"secret")  # type: ignore[arg-type]


def test_set_secret_rejects_blank_secret():
    """Blank secrets should not be persisted."""
    service = _service()

    with pytest.raises(ValueError, match="cannot be blank"):
        service.set_secret("target", "")


def test_set_secret_passes_utf8_bytes_and_expected_metadata():
    """Writing should preserve UTF-8 bytes and expected Credential Manager metadata."""
    captured = {}

    def write(credential_pointer, flags):
        credential = ctypes.cast(
            credential_pointer,
            ctypes.POINTER(credential_module._CREDENTIALW),
        ).contents

        captured["flags"] = flags
        captured["target"] = credential.TargetName
        captured["type"] = credential.Type
        captured["persist"] = credential.Persist
        captured["username"] = credential.UserName
        captured["blob"] = ctypes.string_at(
            credential.CredentialBlob,
            credential.CredentialBlobSize,
        )
        return True

    service = _service(write=write)

    service.set_secret(" target ", "sëcret")

    assert captured == {
        "flags": 0,
        "target": "target",
        "type": 1,
        "persist": 2,
        "username": "OpenWebUI API Key",
        "blob": "sëcret".encode(),
    }


def test_set_secret_raises_for_windows_write_error(monkeypatch):
    """Unexpected Win32 write failures should surface as controlled errors."""
    monkeypatch.setattr(
        credential_module.ctypes,
        "get_last_error",
        lambda: 5,
        raising=False,
    )

    service = _service(write=lambda *_args: False)

    with pytest.raises(credential_module.CredentialStoreError, match=r"error 5"):
        service.set_secret("target", "secret")


def test_delete_secret_returns_when_delete_succeeds():
    """Successful deletion should complete without further action."""
    service = _service(delete=lambda *_args: True)

    service.delete_secret(" target ")


def test_delete_secret_treats_missing_credential_as_success(monkeypatch):
    """Deleting an already absent credential should remain idempotent."""
    monkeypatch.setattr(
        credential_module.ctypes,
        "get_last_error",
        lambda: 1168,
        raising=False,
    )

    service = _service(delete=lambda *_args: False)

    service.delete_secret("target")


def test_delete_secret_raises_for_windows_delete_error(monkeypatch):
    """Unexpected Win32 delete failures should surface as controlled errors."""
    monkeypatch.setattr(
        credential_module.ctypes,
        "get_last_error",
        lambda: 5,
        raising=False,
    )

    service = _service(delete=lambda *_args: False)

    with pytest.raises(credential_module.CredentialStoreError, match=r"error 5"):
        service.delete_secret("target")