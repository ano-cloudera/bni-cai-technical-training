"""Validate the synthetic banking dataset and print a PASS or FAIL summary (exit code 1 on FAIL)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bni_training.data.dictionary import DEFAULT_MANIFEST_DIR, DEFAULT_RAW_DIR
from bni_training.data.validation import validate_dataset


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument(
        "--no-determinism", action="store_true", help="Skip regenerating the dataset to compare bytes"
    )
    parser.add_argument(
        "--partial-scale",
        action="store_true",
        help="Skip the full-size row-count ranges (for scaled test data)",
    )
    args = parser.parse_args(argv)
    report = validate_dataset(
        args.data_dir,
        args.manifest_dir,
        check_determinism=not args.no_determinism,
        expect_full_scale=not args.partial_scale,
    )
    print(report.render())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
