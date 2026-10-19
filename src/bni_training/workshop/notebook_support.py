"""Small notebook helpers for participant identity and executor status.

Lesson logic deliberately stays in the notebooks. These helpers only validate
non-secret runtime labels and print the stable status line used by the runner.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

PARTICIPANT_MODES = ("group_driver", "individual_learning")
PARTICIPANT_REFS = tuple(f"participant_{number:02d}" for number in range(1, 5))


@dataclass(frozen=True)
class ParticipantSettings:
    mode: str
    participant_ref: str


def participant_settings(env: Mapping[str, str] | None = None) -> ParticipantSettings:
    """Read safe anonymous participant settings; never infer a signed-in CAI user."""
    values = os.environ if env is None else env
    mode = values.get("PARTICIPANT_MODE", "group_driver").strip().lower()
    if mode not in PARTICIPANT_MODES:
        raise ValueError("PARTICIPANT_MODE must be group_driver or individual_learning")
    participant_ref = values.get("PARTICIPANT_REF", "participant_01").strip().lower()
    if participant_ref not in PARTICIPANT_REFS:
        raise ValueError("PARTICIPANT_REF must be participant_01 through participant_04")
    return ParticipantSettings(mode, participant_ref)


_SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|BEARER)", re.I)


def load_group_env(path: str | Path, env: dict[str, str] | None = None) -> dict[str, str]:
    """Load a generated, non-secret ``group.env`` into the environment without overriding existing values.

    Secret-looking names are never loaded. Returns the values that were applied.
    """
    target = os.environ if env is None else env
    applied: dict[str, str] = {}
    file = Path(path)
    if not file.is_file():
        return applied
    for line in file.read_text(encoding="utf-8").splitlines():
        found = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if not found or line.lstrip().startswith("#") or _SECRET_NAME.search(found.group(1)):
            continue
        key, value = found.groups()
        if key not in target:
            target[key] = value
            applied[key] = value
    return applied


def lab_status(
    lab_id: str,
    mode: str,
    *,
    passed: int,
    skipped: int = 0,
    failed: int = 0,
) -> None:
    """Print exactly one machine-readable status line for ``execute_notebooks.py``."""
    status = "FAIL" if failed else "PASS"
    print(
        f"LAB_STATUS: lab={lab_id} mode={mode} status={status} "
        f"passed={passed} skipped={skipped} failed={failed}"
    )


__all__ = (
    "PARTICIPANT_MODES",
    "PARTICIPANT_REFS",
    "ParticipantSettings",
    "lab_status",
    "load_group_env",
    "participant_settings",
)
