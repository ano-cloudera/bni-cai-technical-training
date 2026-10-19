"""Create or refresh the ten generated group workspaces under workshop/runtime (dry run unless --apply).

Examples:
  python scripts/prepare_group_workspaces.py                       # show what would happen
  python scripts/prepare_group_workspaces.py --apply               # create / refresh untouched files
  python scripts/prepare_group_workspaces.py --apply --overwrite --yes   # replace edited notebooks (backup)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from bni_training.workshop import group_paths
from bni_training.workshop.workspace_manager import TEMPLATES_DIR, WorkspaceError, WorkspaceManager


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--runtime-dir", type=Path, default=None, help="Default: $WORKSHOP_RUNTIME_DIR or workshop/runtime"
    )
    parser.add_argument("--templates-dir", type=Path, default=TEMPLATES_DIR)
    parser.add_argument(
        "--mode",
        choices=("group_driver", "individual_learning"),
        default="group_driver",
        help="Participant workspace mode (default: group_driver)",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes (the default is a dry run)")
    parser.add_argument(
        "--overwrite", action="store_true", help="Replace participant-edited files (needs --yes; backs up)"
    )
    parser.add_argument("--yes", action="store_true", help="Confirm a destructive --overwrite")
    parser.add_argument("--verbose", action="store_true", help="List every action, not only the summary")
    args = parser.parse_args(argv)
    manager = WorkspaceManager(
        args.runtime_dir or group_paths.runtime_root(),
        args.templates_dir,
        participant_mode=args.mode,
    )
    try:
        actions = manager.sync(apply=args.apply, overwrite=args.overwrite, yes=args.yes)
    except WorkspaceError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    summary = Counter(a.kind for a in actions)
    result = {
        "mode": "apply" if args.apply else "dry-run (nothing was written; add --apply)",
        "runtime_dir": "workshop/runtime" if args.runtime_dir is None else "custom",
        "participant_mode": args.mode,
        "summary": dict(sorted(summary.items())),
    }
    if args.verbose:
        result["actions"] = [a.as_dict() for a in actions]
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
