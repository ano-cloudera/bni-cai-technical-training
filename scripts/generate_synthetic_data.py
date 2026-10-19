"""Generate the fully synthetic workshop banking dataset (deterministic, offline, standard library only).

Examples:
  python scripts/generate_synthetic_data.py --preview
  python scripts/generate_synthetic_data.py --output-dir data/raw --manifest-dir data/manifests
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bni_training.data.synthetic import SEED, generate, preview, write_dataset


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output-dir", type=Path, help="Directory for the five CSV files (required unless --preview)"
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        help="Directory for the JSON manifests (default: <output-dir>/../manifests)",
    )
    parser.add_argument("--seed", type=int, default=SEED, help=f"Random seed (default {SEED})")
    parser.add_argument(
        "--scale", type=float, default=1.0, help="Row-count multiplier; 1.0 is the workshop size"
    )
    parser.add_argument("--preview", action="store_true", help="Print row counts and samples; write nothing")
    args = parser.parse_args(argv)
    if not 0.01 <= args.scale <= 2.0:
        parser.error("--scale must be between 0.01 and 2.0")
    dataset = generate(args.seed, args.scale)
    if args.preview:
        print(json.dumps(preview(dataset), indent=2))
        return 0
    if args.output_dir is None:
        parser.error("--output-dir is required (use --preview to inspect without writing)")
    manifest_dir = args.manifest_dir or args.output_dir.parent / "manifests"
    manifests = write_dataset(dataset, args.output_dir, manifest_dir)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "manifest_dir": str(manifest_dir),
                "row_counts": manifests["dataset_manifest.json"]["row_counts"],
                "total_size_mb": manifests["dataset_manifest.json"]["total_size_mb"],
                "checksums": {k: v["sha256"] for k, v in manifests["checksums.json"]["files"].items()},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
