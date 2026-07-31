"""External updater engine with backup, health check and rollback."""

import argparse
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from auditor_support_tool.core.constants import (
    UPDATE_BACKUP_RETENTION,
    UPDATE_HEALTH_TIMEOUT_SECONDS,
    UPDATE_MANIFEST_NAME,
)


def process_exists(pid: int) -> bool:
    """Return whether a process still exists."""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def wait_for_process_exit(pid: int, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while process_exists(pid):
        if time.monotonic() >= deadline:
            raise RuntimeError("The running application did not close in time.")
        time.sleep(0.25)


def copy_directory(source: Path, target: Path) -> None:
    """Replace target contents with source contents."""

    target.mkdir(parents=True, exist_ok=True)
    for child in list(target.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in source.iterdir():
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination)
        else:
            shutil.copy2(child, destination)


def create_backup(target: Path, backup_root: Path, version: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backup_root / f"before-{version}-{timestamp}"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(target, backup)
    return backup


def prune_backups(backup_root: Path) -> None:
    backups = sorted(
        (path for path in backup_root.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[UPDATE_BACKUP_RETENTION:]:
        shutil.rmtree(old_backup, ignore_errors=True)


def launch_application(
    executable: Path,
    health_marker: Path,
    health_token: str,
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [
            str(executable),
            "--update-health-marker",
            str(health_marker),
            "--update-health-token",
            health_token,
        ],
        cwd=str(executable.parent),
    )


def wait_for_health(marker: Path, process: subprocess.Popen[bytes]) -> bool:
    deadline = time.monotonic() + UPDATE_HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if marker.is_file():
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def restore_backup(backup: Path, target: Path) -> None:
    copy_directory(backup, target)


def run_update(args: argparse.Namespace) -> int:
    source = Path(args.source).resolve()
    target = Path(args.target).resolve()
    backup_root = Path(args.backup_root).resolve()
    health_marker = Path(args.health_marker).resolve()
    app_executable = target / args.app_exe

    wait_for_process_exit(args.wait_pid)
    if not (source / UPDATE_MANIFEST_NAME).is_file():
        raise RuntimeError("The staged update manifest is missing.")

    backup = create_backup(target, backup_root, args.version)
    try:
        copy_directory(source, target)
        health_marker.unlink(missing_ok=True)
        process = launch_application(app_executable, health_marker, args.health_token)
        if not wait_for_health(health_marker, process):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            restore_backup(backup, target)
            subprocess.Popen([str(app_executable)], cwd=str(target))
            return 2
        prune_backups(backup_root)
        shutil.rmtree(source, ignore_errors=True)
        return 0
    except Exception:
        restore_backup(backup, target)
        subprocess.Popen([str(app_executable)], cwd=str(target))
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auditor Support Tool updater")
    parser.add_argument("--wait-pid", type=int, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--backup-root", required=True)
    parser.add_argument("--app-exe", required=True)
    parser.add_argument("--health-marker", required=True)
    parser.add_argument("--health-token", required=True)
    parser.add_argument("--version", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return run_update(args)
