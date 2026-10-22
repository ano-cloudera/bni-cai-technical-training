"""Build the demo notebooks in notebooks/demos/ from their percent-format sources (not part of the 13 labs).

Run with --check to verify that the committed notebooks match their sources.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.build_notebooks import parse_percent_source
from scripts.strip_notebooks import clean

DEMOS_DIR = Path(__file__).resolve().parents[1] / "notebooks" / "demos"


def render(source: Path) -> str:
    return json.dumps(clean(parse_percent_source(source)), indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a notebook is out of date")
    args = parser.parse_args(argv)
    stale = []
    for source in sorted(DEMOS_DIR.glob("*.py")):
        target = source.with_suffix(".ipynb")
        text = render(source)
        if args.check:
            if not target.is_file() or target.read_text() != text:
                stale.append(target.name)
        else:
            target.write_text(text)
            print("wrote", target.name)
    if stale:
        print("out of date:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
