"""Probe the application-level group isolation in a throwaway directory (never touches real workspaces).

This is NOT an OS-level security test: all participants are collaborators in one CAI project.
"""

from __future__ import annotations

import sys

from bni_training.workshop.isolation_check import NOTE, run_probes


def main(argv=None) -> int:
    probes = run_probes()
    for probe in probes:
        print(
            f"[{'PASS' if probe.passed else 'FAIL'}] {probe.name}"
            + (f": {probe.detail}" if probe.detail else "")
        )
    failed = [p for p in probes if not p.passed]
    print(f"RESULT: {'PASS' if not failed else 'FAIL'} ({len(probes) - len(failed)}/{len(probes)} probes)")
    print(f"NOTE: {NOTE}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
