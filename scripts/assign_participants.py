"""Assign about 40 participants to the ten groups (trainer-only output; dry run unless --apply).

The roster is supplied by the trainer at run time (CSV with participant_ref, optionally group_id).
Without a roster the script uses synthetic labels participant-001... Nothing with real names is ever
committed, and no CAI user is created.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from bni_training.data.bundles import BundleCatalog
from bni_training.workshop import group_paths
from bni_training.workshop.roster import (
    DEFAULT_MAX_PER_GROUP,
    RosterError,
    anonymous_refs,
    assign,
    read_roster,
    summarize,
    synthetic_roster,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--roster", type=Path, help="Trainer-supplied CSV (participant_ref[, group_id])")
    parser.add_argument(
        "--count", type=int, default=40, help="Synthetic participants when no roster is given"
    )
    parser.add_argument("--max-per-group", type=int, default=DEFAULT_MAX_PER_GROUP)
    parser.add_argument("--runtime-dir", type=Path, default=None)
    parser.add_argument(
        "--apply", action="store_true", help="Write the assignment under runtime/shared/state"
    )
    args = parser.parse_args(argv)
    try:
        rows = read_roster(args.roster) if args.roster else synthetic_roster(args.count)
        assignment = assign(rows, max_per_group=args.max_per_group)
    except (RosterError, OSError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    catalog = BundleCatalog.load()
    summary = summarize(assignment)
    summary["mode"] = "apply" if args.apply else "dry-run (nothing was written; add --apply)"
    summary["source"] = "trainer roster" if args.roster else "synthetic labels"
    if args.apply:
        root = args.runtime_dir or group_paths.runtime_root()
        target_dir = group_paths.safe_join(root, "shared", "state")
        target_dir.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(
            ["trainer_ref", "participant_ref", "group_id", "dataset_id", "mission_id"]
        )
        for trainer_ref, participant_ref, group in anonymous_refs(assignment):
            bundle = catalog.for_group(group)
            writer.writerow(
                [trainer_ref, participant_ref, group, bundle.dataset_id, bundle.mission_id]
            )
        (target_dir / "participant-assignments.csv").write_text(buffer.getvalue(), encoding="utf-8")
        (target_dir / "participant-assignments.summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        summary["written"] = [
            "shared/state/participant-assignments.csv",
            "shared/state/participant-assignments.summary.json",
        ]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
