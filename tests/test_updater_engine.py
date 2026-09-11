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


@pytest.fixture
def update_run(monkeypatch, tmp_path):
    source = tmp_path / "staged"
    source.mkdir()
    (source / engine.UPDATE_MANIFEST_NAME).write_text("{}")
    args = SimpleNamespace(
        source=str(source),
        target=str(tmp_path / "app"),
        backup_root=str(tmp_path / "backups"),
        health_marker=str(tmp_path / "health"),
        app_exe="app.exe",
        wait_pid=456,
        version="test",
        health_token="test",
    )
    calls = []
    child = Mock()
    child.poll.return_value = None
    child.terminate.side_effect = lambda: calls.append("terminate")
    child.wait.side_effect = lambda **kw: calls.append("stopped")
    child.kill.side_effect = lambda: calls.append("kill")
    mocks = {}
    for name, mock in {
        "wait_for_process_exit": Mock(),
        "create_backup": Mock(return_value=tmp_path / "backup"),
        "copy_directory": Mock(side_effect=lambda *a: calls.append("replace")),
        "launch_application": Mock(return_value=child),
        "wait_for_health": Mock(return_value=True),
        "restore_backup": Mock(side_effect=lambda *a: calls.append("restore")),
        "prune_backups": Mock(),
    }.items():
        monkeypatch.setattr(engine, name, mock)
        mocks[name] = mock
    relaunch = Mock(side_effect=lambda *a, **kw: calls.append("relaunch"))
    monkeypatch.setattr(engine.subprocess, "Popen", relaunch)
    return args, child, calls, mocks, relaunch


def test_update_success_commits(update_run):
    args, child, calls, mocks, relaunch = update_run
    assert engine.run_update(args) == 0
    assert calls == ["replace"]
    mocks["prune_backups"].assert_called_once()
    mocks["restore_backup"].assert_not_called()
    relaunch.assert_not_called()


@pytest.mark.parametrize("cleanup", ["prune", "staged"])
def test_post_commit_cleanup_failure_never_rolls_back(update_run, monkeypatch, caplog, cleanup):
    args, child, calls, mocks, relaunch = update_run
    if cleanup == "prune":
        mocks["prune_backups"].side_effect = PermissionError("unavailable")
    else:
        monkeypatch.setattr(
            engine.shutil, "rmtree", Mock(side_effect=PermissionError("unavailable"))
        )
    assert engine.run_update(args) == 0
    assert calls == ["replace"]
    mocks["restore_backup"].assert_not_called()
    relaunch.assert_not_called()
    assert "Update succeeded" in caplog.text


def test_health_failure_stops_child_before_restore(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].return_value = False
    assert engine.run_update(args) == 2
    assert calls == ["replace", "terminate", "stopped", "restore", "relaunch"]
    mocks["prune_backups"].assert_not_called()
    assert engine.Path(args.source).exists()


def test_wait_error_also_stops_child_before_restore(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].side_effect = OSError("health failed")
    with pytest.raises(RuntimeError, match="previous installation was restored"):
        engine.run_update(args)
    assert calls.index("stopped") < calls.index("restore")


def test_kill_fallback_is_waited_before_restore(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].return_value = False

    def wait(**kwargs):
        calls.append("wait")
        if calls.count("wait") == 1:
            raise engine.subprocess.TimeoutExpired("child", 5)

    child.wait.side_effect = wait
    assert engine.run_update(args) == 2
    assert calls == ["replace", "terminate", "wait", "kill", "wait", "restore", "relaunch"]


def test_unconfirmed_child_exit_prevents_restore(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].return_value = False
    child.wait.side_effect = engine.subprocess.TimeoutExpired("child", 5)
    with pytest.raises(RuntimeError, match="Backup retained"):
        engine.run_update(args)
    mocks["restore_backup"].assert_not_called()
    relaunch.assert_not_called()


def test_restore_failure_preserves_original_error_and_backup(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].side_effect = OSError("health failed")
    mocks["restore_backup"].side_effect = OSError("restore failed")
    with pytest.raises(RuntimeError) as caught:
        engine.run_update(args)
    assert "health failed" in str(caught.value)
    assert "restore failed" in str(caught.value)
    assert "Backup retained" in str(caught.value)
    mocks["restore_backup"].assert_called_once()
    mocks["prune_backups"].assert_not_called()
    relaunch.assert_not_called()


def test_prune_failure_leaves_retained_backups_untouched(tmp_path, monkeypatch):
    import os

    for i in range(engine.UPDATE_BACKUP_RETENTION + 2):
        folder = tmp_path / str(i)
        folder.mkdir()
        (folder / "evidence").write_bytes(b"retained")
        os.utime(folder, (100 + i, 100 + i))

    def fail(path):
        assert int(path.name) < 2
        raise PermissionError("cannot delete old backup")

    monkeypatch.setattr(engine.shutil, "rmtree", fail)
    with pytest.raises(PermissionError):
        engine.prune_backups(tmp_path)
    for i in range(2, engine.UPDATE_BACKUP_RETENTION + 2):
        assert (tmp_path / str(i) / "evidence").read_bytes() == b"retained"


@pytest.mark.parametrize("failure", ["copy_directory", "launch_application"])
def test_failure_before_child_creation_restores_once(update_run, failure):
    args, child, calls, mocks, relaunch = update_run
    mocks[failure].side_effect = OSError("installation failed")
    with pytest.raises(RuntimeError, match="previous installation was restored"):
        engine.run_update(args)
    child.terminate.assert_not_called()
    mocks["restore_backup"].assert_called_once()
    relaunch.assert_called_once()


def test_already_stopped_child_is_not_terminated(update_run):
    args, child, calls, mocks, relaunch = update_run
    child.poll.return_value = 1
    mocks["wait_for_health"].return_value = False
    assert engine.run_update(args) == 2
    child.terminate.assert_not_called()
    assert calls == ["replace", "restore", "relaunch"]


def test_failed_restart_reports_restored_state_without_second_restore(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].return_value = False
    relaunch.side_effect = OSError("launch unavailable")
    with pytest.raises(
        RuntimeError, match="previous installation was restored.*could not be restarted"
    ):
        engine.run_update(args)
    mocks["restore_backup"].assert_called_once()
    mocks["prune_backups"].assert_not_called()


def test_termination_failure_leaves_backup_and_installation_for_recovery(update_run):
    args, child, calls, mocks, relaunch = update_run
    mocks["wait_for_health"].return_value = False
    child.terminate.side_effect = PermissionError("cannot stop child")
    with pytest.raises(RuntimeError, match="Backup retained"):
        engine.run_update(args)
    mocks["restore_backup"].assert_not_called()
    mocks["prune_backups"].assert_not_called()
    relaunch.assert_not_called()
