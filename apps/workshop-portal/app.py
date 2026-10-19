"""Streamlit entrypoint of the shared Workshop Portal. The logic lives in bni_training.workshop.portal."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bni_training.workshop.portal.ui import render  # noqa: E402

render()
