"""Win32 wait safety: mock the API, never terminate real processes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from auditor_support_tool.services import updater_engine as engine


@pytest.fixture
def win32(monkeypatch):
    api = SimpleNamespace(
        OpenProcess=Mock(return_value=123),
        WaitForSingleObject=Mock(return_value=0),
        CloseHandle=Mock(return_value=1),
    )
    monkeypatch.setattr(engine, "_windows_api", lambda: api)
    monkeypatch.setattr(engine.os, "name", "nt")
    monkeypatch.setattr(
        engine.os, "kill", Mock(side_effect=AssertionError("No signals on Windows"))
    )
    monkeypatch.setattr(engine.ctypes, "get_last_error", lambda: 5)
    return api


def test_exits_normally_and_closes_handle(win32):
    engine.wait_for_process_exit(456, 3)
    win32.OpenProcess.assert_called_once_with(0x00100000, False, 456)
    win32.WaitForSingleObject.assert_called_once_with(123, 3000)
    win32.CloseHandle.assert_called_once_with(123)
    engine.os.kill.assert_not_called()


def test_already_exited(win32, monkeypatch):
    win32.OpenProcess.return_value = 0
    monkeypatch.setattr(engine.ctypes, "get_last_error", lambda: 87)
    engine.wait_for_process_exit(456)
    assert engine.process_exists(456) is False
    win32.WaitForSingleObject.assert_not_called()
    win32.CloseHandle.assert_not_called()


@pytest.mark.parametrize("pid", [0, -1, 2**32])
def test_invalid_pid_fails_safely(win32, pid):
    with pytest.raises(RuntimeError, match="PID"):
        engine.wait_for_process_exit(pid)
    win32.OpenProcess.assert_not_called()


def test_access_failure_is_not_exit(win32):
    win32.OpenProcess.return_value = 0
    with pytest.raises(RuntimeError, match="Cannot open"):
        engine.wait_for_process_exit(456)
    win32.CloseHandle.assert_not_called()


@pytest.mark.parametrize("status", [258, 0xFFFFFFFF])
def test_wait_failure_closes_handle(win32, status):
    win32.WaitForSingleObject.return_value = status
    with pytest.raises(RuntimeError):
        engine.wait_for_process_exit(456)
    win32.CloseHandle.assert_called_once_with(123)
    engine.os.kill.assert_not_called()


def test_live_probe_uses_zero_timeout_without_signals(win32):
    win32.WaitForSingleObject.return_value = 258
    assert engine.process_exists(456)
    win32.WaitForSingleObject.assert_called_once_with(123, 0)
    win32.CloseHandle.assert_called_once_with(123)
    engine.os.kill.assert_not_called()


def test_timeout_stops_before_installation_mutation(win32, monkeypatch, tmp_path):
    win32.WaitForSingleObject.return_value = 258
    backup = Mock(side_effect=AssertionError("must not back up or replace"))
    copy = Mock(side_effect=AssertionError("must not replace files"))
    monkeypatch.setattr(engine, "create_backup", backup)
    monkeypatch.setattr(engine, "copy_directory", copy)
    args = SimpleNamespace(
        source=str(tmp_path / "source"),
        target=str(tmp_path / "target"),
        backup_root=str(tmp_path / "backups"),
        health_marker=str(tmp_path / "health"),
        app_exe="app.exe",
        wait_pid=456,
    )
    with pytest.raises(RuntimeError, match="did not close"):
        engine.run_update(args)
    backup.assert_not_called()
    copy.assert_not_called()


def test_close_failure_reported(win32):
    win32.CloseHandle.return_value = 0
    with pytest.raises(RuntimeError, match="close the process wait handle"):
        engine.wait_for_process_exit(456)
