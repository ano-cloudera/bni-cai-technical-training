"""Clone the committed HEAD into a temporary directory and check that it is clean and self-consistent.

Checks: no forbidden or generated files are tracked, no real local path or secret is tracked, the dataset
validates, the notebooks are stripped, the default topology plans single_project, and running them leaves the
clone unmodified. Prints one line per check and a final ``CLEAN_CLONE: PASS`` or ``CLEAN_CLONE: FAIL``.
Exit codes: 0 PASS, 1 FAIL. Nothing is pushed and no service is contacted.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = ("__pycache__", ".pyc", ".DS_Store", ".egg-info", ".pytest_cache", ".ruff_cache")
FORBIDDEN_PREFIXES = ("build/", "dist/", "workshop/runtime/", "wheelhouse/")


def forbidden_tracked(files: list[str]) -> list[str]:
    return [
        f
        for f in files
        if any(part in f for part in FORBIDDEN_PARTS)
        or f.startswith(FORBIDDEN_PREFIXES)
        or Path(f).name in {".env", "group.env"}
    ]


def run(clone: Path, *cmd: str, env: dict | None = None) -> subprocess.CompletedProcess:
    environment = {k: v for k, v in os.environ.items() if k != "WORKSHOP_TOPOLOGY"}
    environment.update({"PYTHONPATH": "src:.", "PYTHONDONTWRITEBYTECODE": "1", **(env or {})})
    return subprocess.run(cmd, cwd=clone, env=environment, capture_output=True, text=True, timeout=1800)


def git(clone: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=clone, capture_output=True, text=True).stdout


def checks(clone: Path) -> list[tuple[str, bool, str]]:
    py = sys.executable
    tracked = [n for n in git(clone, "ls-files").splitlines() if n]
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    bad = forbidden_tracked(tracked)
    add("no cache, build or runtime file is tracked", not bad, ", ".join(bad[:5]))
    add("the clone starts clean", not git(clone, "status", "--porcelain").strip())
    audit = run(clone, py, "scripts/audit_local_paths.py")
    add("no real local path is tracked", audit.returncode == 0, audit.stdout.strip().splitlines()[-1])
    secrets = run(clone, py, "scripts/secret_scan.py")
    add("secret scan", secrets.returncode == 0, secrets.stdout.strip()[-120:])
    dataset = run(clone, py, "scripts/validate_dataset.py")
    add("dataset validates", dataset.returncode == 0, dataset.stdout.strip().splitlines()[-1])
    stripped = run(clone, py, "scripts/strip_notebooks.py", "--check")
    add("notebooks are stripped", stripped.returncode == 0, stripped.stdout.strip()[-120:].split("\n")[-1])
    plan = clone / "plan.json"
    planned = run(
        clone, py, "-m", "automation.cai_api_v2.cli", "--config", "config/env.local.example.yaml",
        "plan", "--output", str(plan),
    )  # fmt: skip
    topology = json.loads(plan.read_text())["topology"] if planned.returncode == 0 else "error"
    plan.unlink(missing_ok=True)
    add("the default plan is single_project", topology == "single_project", topology)
    after = git(clone, "status", "--porcelain").strip()
    add("the checks left the clone unmodified", not after, after[:120])
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT, help="repository whose HEAD is cloned")
    parser.add_argument("--keep", action="store_true", help="keep the temporary clone")
    args = parser.parse_args(argv)
    work = Path(tempfile.mkdtemp(prefix="bni-clean-clone-"))
    try:
        clone = work / "clone"
        cloned = subprocess.run(
            ["git", "clone", "-q", str(args.source), str(clone)], capture_output=True, text=True
        )
        if cloned.returncode:
            print(f"[FAIL] clone: {cloned.stderr.strip()[-200:]}")
            print("CLEAN_CLONE: FAIL")
            return 1
        results = checks(clone)
        dirty = git(args.source, "status", "--porcelain").strip()
        if dirty:
            results.append(
                ("the source working tree has uncommitted changes (not part of the clone)", False, "")
            )
        for name, ok, detail in results:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))
        overall = all(ok for _name, ok, _detail in results)
        print(f"CLEAN_CLONE: {'PASS' if overall else 'FAIL'}")
        return 0 if overall else 1
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
