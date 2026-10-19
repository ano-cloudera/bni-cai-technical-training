"""rc1 compatibility wrapper. The canonical lab is scripts/09_phoenix_monitoring.py (see config/workshop/labs.yaml)."""

from __future__ import annotations

import sys

from bni_training.lab_registry import delegate


def main(argv=None) -> int:
    return delegate("scripts/09_phoenix_observability.py", argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
