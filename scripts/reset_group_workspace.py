"""Reset ONE group's generated files (dry run unless --yes). Never touches another group or shared files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bni_training.workshop import group_paths
from bni_training.workshop.workspace_manager import TEMPLATES_DIR, WorkspaceError, WorkspaceManager


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--group-id", required=True, help="group_01 ... group_10 (required, no default)")
    parser.add_argument(
        "--include-notebooks", action="store_true", help="Also restore notebooks (edited ones are backed up)"
    )
    parser.add_argument("--yes", action="store_true", help="Actually reset; without it this is a dry run")
    parser.add_argument("--runtime-dir", type=Path, default=None)
    parser.add_argument("--templates-dir", type=Path, default=TEMPLATES_DIR)
    args = parser.parse_args(argv)
    manager = WorkspaceManager(args.runtime_dir or group_paths.runtime_root(), args.templates_dir)
    try:
        actions = manager.reset(
            args.group_id, include_notebooks=args.include_notebooks, apply=args.yes, yes=args.yes
        )
    except WorkspaceError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "mode": "reset" if args.yes else "dry-run (add --yes to reset)",
                "actions": [a.as_dict() for a in actions],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
