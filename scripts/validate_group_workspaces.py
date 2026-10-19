"""Validate the generated group workspaces (structure, group.env, mission, notebooks, symlinks, secrets)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bni_training.workshop import group_paths
from bni_training.workshop.workspace_manager import TEMPLATES_DIR, WorkspaceError, WorkspaceManager


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runtime-dir", type=Path, default=None)
    parser.add_argument("--templates-dir", type=Path, default=TEMPLATES_DIR)
    args = parser.parse_args(argv)
    manager = WorkspaceManager(args.runtime_dir or group_paths.runtime_root(), args.templates_dir)
    try:
        report = manager.validate()
    except WorkspaceError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(report.render())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
