"""Exercise the version script only against disposable project copies."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("invalid", [None, "missing", "duplicate"])
def test_set_version_copy(tmp_path, invalid):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell required")
    root = Path(__file__).resolve().parents[1]
    names = [
        "src/auditor_support_tool/core/constants.py",
        "pyproject.toml",
        "src/auditor_support_tool/__init__.py",
        "scripts/set_version.ps1",
    ]
    real_before = {name: (root / name).read_bytes() for name in names}
    for name in names:
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(real_before[name])
    init = tmp_path / names[2]
    if invalid == "missing":
        init.write_text("# no version assignment\n", encoding="utf-8")
    elif invalid == "duplicate":
        init.write_text('__version__ = "1"\n__version__ = "2"\n', encoding="utf-8")
    before = {name: (tmp_path / name).read_bytes() for name in names}
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(tmp_path / names[3]),
            "-Version",
            "0.1.3-beta.3",
        ],
        capture_output=True,
        text=True,
    )
    if invalid:
        assert result.returncode != 0
        assert "Expected exactly one" in result.stderr
        assert before == {name: (tmp_path / name).read_bytes() for name in names}
    else:
        assert result.returncode == 0, result.stderr
        for name, key in zip(names[:3], ["APP_VERSION", "version", "__version__"], strict=True):
            assert f'{key} = "0.1.3-beta.3"' in (tmp_path / name).read_text(encoding="utf-8")
    assert real_before == {name: (root / name).read_bytes() for name in names}
