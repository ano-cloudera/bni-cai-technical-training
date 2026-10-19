"""rc1 compatibility wrapper. The canonical lab is scripts/08_agent_workflow.py (see config/workshop/labs.yaml)."""

from __future__ import annotations

import sys

from bni_training.lab_registry import delegate


def main(argv=None) -> int:
    return delegate("scripts/08_multi_agent_workflow.py", argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
