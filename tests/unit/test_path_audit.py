"""The path audit fails on real paths and stays quiet on its own code and on placeholders."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bni_training import path_audit
from bni_training.path_audit import audit, scan_text

ROOT = Path(__file__).resolve().parents[2]
S = "/"
# Dirty samples are assembled at runtime, so this file contains none of them.
DIRTY = {
    "macos-home": S + "Users" + S + "jordan" + S + "work" + S + "app",
    "linux-home": S + "home" + S + "jordan" + S + "work",
    "private-scratch": S + "private" + S + "var" + S + "folders" + S + "zz" + S + "T" + S + "x",
    "var-folders": S + "var" + S + "folders" + S + "zz" + S + "T",
    "windows-profile": "C:" + "\\" + "Users" + "\\" + "jordan" + "\\" + "docs",
}
CLEAN = [
    S + "Users" + S + "<name>" + S + "project",
    S + "Users" + S + "$USER" + S + "project",
    S + "home" + S + "cdsw" + S + "workshop",
    "the " + "Users" + " folder and the home folder are not paths",
    "src/bni_training/path_audit.py",
    "workshop/runtime/groups/group_01/notebooks",
    "https://example.com/Users/profile",
]


@pytest.mark.parametrize("kind", sorted(DIRTY))
def test_every_kind_of_real_local_path_is_found(kind) -> None:
    found = scan_text(f"value = '{DIRTY[kind]}'\n", "x.py")
    assert [f.kind for f in found] == [kind] and found[0].line == 1 and found[0].path == "x.py"


@pytest.mark.parametrize("text", CLEAN)
def test_placeholders_and_bare_directory_names_are_not_findings(text) -> None:
    assert scan_text(text) == []


def test_findings_report_the_location_and_never_the_matched_text() -> None:
    found = scan_text("ok\n" + DIRTY["macos-home"] + "\n")
    assert found[0].line == 2 and "jordan" not in str(found[0])


def test_the_scanner_does_not_trigger_on_its_own_implementation_or_tests() -> None:
    own = [ROOT / "src/bni_training/path_audit.py", ROOT / "scripts/audit_local_paths.py", Path(__file__)]
    assert path_audit.scan_files(ROOT, own) == []


def test_the_whole_tracked_tree_is_clean() -> None:
    ok, findings = audit(ROOT)
    assert ok, [str(f) for f in findings]


def make_repo(tmp_path: Path, files: dict[str, str], track: bool = True) -> Path:
    for name, text in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    if track:
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        subprocess.run([*git, "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def test_a_dirty_tracked_file_fails_the_audit_in_any_directory(tmp_path) -> None:
    repo = make_repo(tmp_path, {"docs/deep/note.md": f"see {DIRTY['macos-home']}\n", "ok.txt": "fine\n"})
    ok, findings = audit(repo)
    assert not ok and [(f.path, f.kind) for f in findings] == [("docs/deep/note.md", "macos-home")]


def test_a_clean_tree_passes(tmp_path) -> None:
    ok, findings = audit(make_repo(tmp_path, {"a.md": "nothing here\n", "b/c.py": "x = 1\n"}))
    assert ok and findings == []


def test_untracked_files_are_outside_the_tracked_audit(tmp_path) -> None:
    repo = make_repo(tmp_path, {"a.md": "clean\n"})
    (repo / "scratch.txt").write_text(DIRTY["linux-home"])
    assert audit(repo)[0] is True


def test_without_git_every_file_except_caches_is_scanned(tmp_path) -> None:
    repo = make_repo(
        tmp_path, {"src/x.py": DIRTY["var-folders"], "build/skip.txt": DIRTY["var-folders"]}, track=False
    )
    assert [f.path for f in audit(repo)[1]] == ["src/x.py"]


def test_binary_files_are_skipped(tmp_path) -> None:
    repo = make_repo(tmp_path, {"a.md": "x\n"})
    (repo / "blob.bin").write_bytes(b"\0" + DIRTY["macos-home"].encode())
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert audit(repo)[0] is True


def test_the_command_line_exits_non_zero_on_findings_and_reports_the_status(tmp_path) -> None:
    command = [sys.executable, str(ROOT / "scripts/audit_local_paths.py"), "--json"]
    dirty = make_repo(tmp_path / "dirty", {"n.md": DIRTY["macos-home"]})
    result = subprocess.run([*command, "--root", str(dirty)], capture_output=True, text=True)
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "FAIL"
    clean = make_repo(tmp_path / "clean", {"n.md": "ok"})
    result = subprocess.run([*command, "--root", str(clean)], capture_output=True, text=True)
    assert result.returncode == 0 and json.loads(result.stdout)["status"] == "PASS"
