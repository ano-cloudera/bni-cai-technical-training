"""The clean-clone validator reports PASS for a good commit and FAIL when a real local path is tracked."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_clean_clone as vcc  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]


def test_generated_and_local_files_are_forbidden_in_the_tracked_set() -> None:
    bad = ["src/__pycache__/x.cpython-310.pyc", "build/plan.json", ".DS_Store", "workshop/runtime/a.txt"]
    bad += ["workshop/runtime/groups/group_01/config/group.env", ".env"]
    assert vcc.forbidden_tracked(bad) == bad


def test_source_templates_and_examples_are_allowed() -> None:
    good = ["workshop/templates/group/group.env.example", ".env.example", "src/bni_training/labs.py"]
    good += ["notebooks/templates/00_environment_validation.ipynb", "workshop/README.md"]
    assert vcc.forbidden_tracked(good) == []


@pytest.fixture(scope="module")
def head_clone(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("source") / "repo"
    subprocess.run(["git", "clone", "-q", str(ROOT), str(path)], check=True)
    return path


def run_validator(source: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_clean_clone.py"), "--source", str(source)],
        capture_output=True,
        text=True,
        timeout=900,
    )


def test_a_good_commit_reports_an_overall_pass(head_clone) -> None:
    result = run_validator(head_clone)
    assert result.returncode == 0, result.stdout
    assert result.stdout.strip().splitlines()[-1] == "CLEAN_CLONE: PASS"
    assert "[FAIL]" not in result.stdout


def test_a_committed_real_local_path_makes_the_overall_status_fail(head_clone, tmp_path) -> None:
    dirty = tmp_path / "dirty"
    subprocess.run(["git", "clone", "-q", str(head_clone), str(dirty)], check=True)
    (dirty / "docs").mkdir(exist_ok=True)
    (dirty / "docs" / "oops.md").write_text("open " + "/" + "Users" + "/jordan/work/app\n")
    subprocess.run(["git", "add", "-A"], cwd=dirty, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "dirty"], cwd=dirty, check=True)
    result = run_validator(dirty)
    assert result.returncode == 1
    assert "[FAIL] no real local path is tracked" in result.stdout
    assert result.stdout.strip().splitlines()[-1] == "CLEAN_CLONE: FAIL"
    assert "jordan" not in result.stdout


def test_uncommitted_changes_in_the_source_fail_the_validation(head_clone) -> None:
    (head_clone / "scratch.txt").write_text("x")
    try:
        result = run_validator(head_clone)
    finally:
        (head_clone / "scratch.txt").unlink()
    assert result.returncode == 1 and "uncommitted changes" in result.stdout
