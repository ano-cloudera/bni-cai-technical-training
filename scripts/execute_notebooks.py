"""Execute notebooks for real with nbclient and refuse to let unfinished cells pass silently.

A notebook passes only when every code cell executed without error AND it printed exactly one
``LAB_STATUS:`` line whose status is PASS or SKIPPED. A FAIL, a missing status line, an unexecuted
code cell, or an unfinished-work marker (TODO, FIXME, NotImplementedError) fails the run.
Executed copies go to the report directory; the source notebooks are never modified.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

STATUS = re.compile(
    r"LAB_STATUS: lab=(\S+) mode=(\S+) status=(PASS|SKIPPED|FAIL) passed=(\d+) skipped=(\d+) failed=(\d+)"
)
UNFINISHED = re.compile(r"\b(TODO|FIXME|XXX)\b|NotImplementedError")


def output_text(cell) -> str:
    chunks = []
    for output in cell.get("outputs", []):
        if output.get("output_type") == "stream":
            chunks.append(output.get("text", ""))
        elif output.get("output_type") == "error":
            chunks.append(f"{output.get('ename')}: {output.get('evalue')}")
    return "".join(chunks)


def verify(notebook, name: str) -> dict:
    problems: list[str] = []
    statuses = []
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        if UNFINISHED.search(cell.source):
            problems.append(f"cell {index}: unfinished-work marker in source")
        if cell.get("execution_count") is None:
            problems.append(f"cell {index}: code cell was not executed")
        statuses.extend(STATUS.findall(output_text(cell)))
    if len(statuses) != 1:
        problems.append(f"expected exactly one LAB_STATUS line, found {len(statuses)}")
    status = statuses[0] if statuses else None
    if status and status[2] == "FAIL":
        problems.append("lab reported status=FAIL")
    return {
        "notebook": name,
        "lab_status": status[2] if status else None,
        "passed": int(status[3]) if status else 0,
        "skipped": int(status[4]) if status else 0,
        "failed": int(status[5]) if status else 0,
        "problems": problems,
        "result": "FAIL" if problems else "PASS",
    }


def execute(path: Path, out_dir: Path, mode: str, timeout: int) -> dict:
    notebook = nbformat.read(path, as_version=4)
    env_before = os.environ.get("LAB_MODE")
    os.environ["LAB_MODE"] = mode
    try:
        client = NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(path.parent)}},
        )
        client.execute()
    except CellExecutionError as exc:
        return {
            "notebook": path.name,
            "lab_status": None,
            "problems": [f"cell error: {str(exc)[-400:]}"],
            "result": "FAIL",
        }
    finally:
        if env_before is None:
            os.environ.pop("LAB_MODE", None)
        else:
            os.environ["LAB_MODE"] = env_before
    out_dir.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, out_dir / path.name)
    return verify(notebook, path.name)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--mode", choices=["local", "cai"], default="local")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per cell")
    parser.add_argument("--report-dir", type=Path, default=Path("build/notebooks"))
    parser.add_argument(
        "--legacy", action="store_true", help="Also run the rc1 notebooks in notebooks/*.ipynb"
    )
    args = parser.parse_args(argv)
    if args.paths:
        paths = args.paths
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
        from bni_training.lab_registry import canonical_labs

        paths = [lab.notebook_path for lab in canonical_labs()]  # the registry, not a glob, decides
        if args.legacy:
            paths += sorted(Path("notebooks").glob("*.ipynb"))
    results = []
    for path in paths:
        result = execute(path, args.report_dir, args.mode, args.timeout)
        results.append(result)
        detail = result.get("lab_status") or "-"
        print(
            f"{result['result']} {path.name} lab_status={detail}"
            + "".join(f"\n    - {p}" for p in result["problems"])
        )
    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / "notebook-validation.json").write_text(json.dumps(results, indent=2) + "\n")
    failed = [r for r in results if r["result"] == "FAIL"]
    print(f"{len(results) - len(failed)} passed (including SKIPPED labs), {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
