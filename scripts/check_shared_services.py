"""Check the health of the shared services (read-only; never starts, stops, or deploys anything).

Status per service: PASS, FAIL, or SKIPPED. Use --phase to mark services optional or inactive for a
workshop phase (day1, day2_morning, agent_studio_publication). Secrets are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from bni_training.workshop.service_checks import SERVICES, check_services, overall


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("local", "cai"), default=os.environ.get("LAB_MODE", "cai"))
    parser.add_argument("--phase", help="day1 | day2_morning | agent_studio_publication")
    parser.add_argument("--services", default=",".join(SERVICES), help="Comma-separated subset")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)
    services = tuple(s.strip() for s in args.services.split(",") if s.strip())
    try:
        results = check_services(
            os.environ, services=services, phase=args.phase, mode=args.mode, timeout=args.timeout
        )
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    status = overall(results)
    print(
        json.dumps(
            {
                "overall": status,
                "mode": args.mode,
                "phase": args.phase,
                "services": [r.as_dict() for r in results],
            },
            indent=2,
        )
    )
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
