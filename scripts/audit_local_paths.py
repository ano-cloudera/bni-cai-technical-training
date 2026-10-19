"""Fail if any tracked file contains a real machine-specific path (home directory, scratch folder).

Usage: python scripts/audit_local_paths.py [--root DIR] [--json]
Exit codes: 0 clean, 1 findings. Only locations are printed, never the matched text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bni_training.path_audit import audit  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ok, findings = audit(args.root)
    if args.json:
        print(json.dumps({"status": "PASS" if ok else "FAIL", "findings": [str(f) for f in findings]}))
    else:
        for finding in findings:
            print(finding)
        print(f"PATH_AUDIT: {'PASS' if ok else 'FAIL'} ({len(findings)} finding(s))")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
