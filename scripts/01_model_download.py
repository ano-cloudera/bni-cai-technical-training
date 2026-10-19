"""rc1 compatibility wrapper. The canonical lab is scripts/01_model_artifact_validation.py (see config/workshop/labs.yaml)."""

from __future__ import annotations

import sys

from bni_training.lab_registry import delegate


def main(argv=None) -> int:
    return delegate("scripts/01_model_download.py", argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
