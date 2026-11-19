from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent / "fixtures" / "student_demo"


def test_cli_build_and_check(tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-m", "archmap", "build", str(ROOT), "--out", str(out)],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (out / "architecture.json").exists()
    assert (out / "architecture.html").exists()
    bundle = json.loads((out / "architecture.json").read_text(encoding="utf-8"))
    assert bundle["kind"] == "archmap.bundle"
    check = subprocess.run(
        [sys.executable, "-m", "archmap", "check", str(out / "architecture.json")],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    structured = subprocess.run(
        [sys.executable, "-m", "archmap", "check", str(out / "architecture.json"), "--json"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert structured.returncode == 0, structured.stdout + structured.stderr
    payload = json.loads(structured.stdout)
    assert payload["ok"] is True
    assert payload["issueCount"] == 0
    assert payload["issues"] == []


def test_cli_version_uses_package_version() -> None:
    from archmap import __version__

    result = subprocess.run(
        [sys.executable, "-m", "archmap", "--version"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"archmap {__version__}"
