"""The GPU preflight script is read-only, never fails the shell and reports what is missing."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/preflight_gpu_env.sh"


def test_the_script_has_valid_shell_syntax_and_is_executable() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0
    assert os.access(SCRIPT, os.X_OK)


def test_the_script_changes_nothing_and_prints_no_secrets() -> None:
    commands = "\n".join(
        line for line in SCRIPT.read_text().splitlines() if not line.lstrip().startswith("#")
    )
    for forbidden in (
        r"\brm\b",
        r"pip install",
        r"git (push|pull|checkout|reset|fetch)",
        r"\bmkdir\b",
        r"\bchmod\b",
        r"curl .*(-X|--data|-d )",
        r"\bwget\b",
        r"_KEY|TOKEN|PASSWORD",
    ):
        assert not re.search(forbidden, commands), forbidden


def test_the_script_reports_missing_pieces_and_exits_zero(tmp_path) -> None:
    env = {
        **os.environ,
        "REPO": str(tmp_path / "no-repo"),
        "VENV": str(tmp_path / "no-venv"),
        "MODEL_PATH": str(tmp_path / "no-model"),
        "PREFLIGHT_SKIP_NETWORK": "1",
    }
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=env, timeout=60)
    assert result.returncode == 0
    for section in ("== 1.", "== 2.", "== 3.", "== 4.", "== 5.", "== 6.", "== done"):
        assert section in result.stdout, section
    assert "CHECK   no venv at" in result.stdout and "CHECK   no config.json at" in result.stdout
