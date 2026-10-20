"""Strip notebooks to a clean, reviewable state and report anything that must not be committed.

Removes cell outputs, execution counts, execution timestamps and all cell or notebook metadata except the
kernelspec and language name. ``--check`` changes nothing and fails if a notebook is not already clean or
contains a local path, an endpoint, a token, or a timestamp.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bni_training.path_audit import PATTERNS as PATH_PATTERNS  # noqa: E402

# A notebook must not name a real machine path, and must not hard-code a scratch folder either.
LOCAL_PATH = re.compile("|".join([*(p.pattern for p in PATH_PATTERNS.values()), "/" + "tmp" + "/"]))
ALLOWED_NOTEBOOK_METADATA = {"kernelspec", "language_info"}
ALLOWED_LANGUAGE_INFO = {"name", "version"}
FORBIDDEN = {
    "local-path": LOCAL_PATH,
    "endpoint": re.compile(r"(?:https?://|127\.0\.0\.1|localhost|\b\d{1,3}(?:\.\d{1,3}){3}\b)", re.I),
    "token": re.compile(
        r"(?:Bearer\s+\S{8,}|\bsk-[A-Za-z0-9_-]{8,}|(?:api[_-]?key|token|password|secret)\s*[:=]\s*['\"][^'\"]{4,})",
        re.I,
    ),
    "timestamp": re.compile(r"\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d"),
    "env-value": re.compile(r"os\.environ\[['\"][A-Z_]+['\"]\]\s*=\s*['\"]"),
}


def clean(doc: dict) -> dict:
    doc["metadata"] = {k: v for k, v in doc.get("metadata", {}).items() if k in ALLOWED_NOTEBOOK_METADATA}
    info = doc["metadata"].get("language_info")
    if info:
        doc["metadata"]["language_info"] = {k: v for k, v in info.items() if k in ALLOWED_LANGUAGE_INFO}
    for cell in doc["cells"]:
        cell["metadata"] = {}
        cell.pop("attachments", None)
        if cell["cell_type"] == "code":
            cell["outputs"] = []
            cell["execution_count"] = None
    return doc


def findings(doc: dict) -> list[str]:
    text = json.dumps(doc)
    return [name for name, pattern in FORBIDDEN.items() if pattern.search(text)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if anything would change")
    args = parser.parse_args(argv)
    status = 0
    defaults = [*Path("notebooks/legacy").glob("*.ipynb"), *Path("notebooks/templates").glob("*.ipynb")]
    for path in args.paths or sorted(defaults):
        original = path.read_text()
        doc = json.loads(original)
        cleaned = json.dumps(clean(json.loads(original)), indent=1) + "\n"
        problems = findings(doc)
        dirty = cleaned != original
        if args.check:
            note = ("not clean" if dirty else "") + (f" contains {problems}" if problems else "")
            print(f"{'FAIL' if note else 'PASS'} {path.name} {note}".rstrip())
            status |= 1 if (dirty or problems) else 0
        else:
            path.write_text(cleaned)
            print(
                f"{'stripped' if dirty else 'clean'} {path.name}" + (f" FOUND {problems}" if problems else "")
            )
            status |= 1 if problems else 0
    return status


if __name__ == "__main__":
    sys.exit(main())
