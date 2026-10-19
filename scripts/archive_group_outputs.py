"""Archive a group's saved outputs into the trainer-only shared/state/archives (dry run unless --apply)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bni_training.data.bundles import GROUP_IDS
from bni_training.workshop import group_paths
from bni_training.workshop.workspace_manager import TEMPLATES_DIR, WorkspaceError, WorkspaceManager


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--group-id", help="One group, group_01 ... group_10")
    target.add_argument("--all", action="store_true", help="All ten groups")
    parser.add_argument(
        "--participant-ref",
        help="Archive one anonymous participant folder (requires --group-id)",
    )
    parser.add_argument("--include-logs", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Write the zip archive(s)")
    parser.add_argument("--runtime-dir", type=Path, default=None)
    parser.add_argument("--templates-dir", type=Path, default=TEMPLATES_DIR)
    args = parser.parse_args(argv)
    if args.all and args.participant_ref:
        parser.error("--participant-ref requires --group-id")
    manager = WorkspaceManager(args.runtime_dir or group_paths.runtime_root(), args.templates_dir)
    groups = list(GROUP_IDS) if args.all else [args.group_id]
    try:
        results = [
            manager.archive(
                g,
                participant_ref=args.participant_ref,
                include_logs=args.include_logs,
                apply=args.apply,
            )
            for g in groups
        ]
    except WorkspaceError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {"mode": "apply" if args.apply else "dry-run (add --apply)", "archives": results}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
