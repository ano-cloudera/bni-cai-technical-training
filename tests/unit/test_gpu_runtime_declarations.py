"""The GPU profiles declare the runtime dependencies that the CAI sandbox validation found missing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("PyYAML", "packaging", "requests", "certifi", "urllib3", "cachetools", "cloudpickle")


def declared(path: Path) -> set[str]:
    names = set()
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.add(re.split(r"[=<>!~\[ ;]", line)[0])
    return names


@pytest.mark.parametrize("profile", ["gpu-l40s", "gpu-h200"])
def test_gpu_inputs_declare_the_required_runtime_dependencies_and_keep_vllm_pinned(profile) -> None:
    names = declared(ROOT / f"requirements/{profile}.in")
    assert set(REQUIRED) <= names and "vllm" in names
    assert "vllm==0.29.0" in (ROOT / f"requirements/{profile}.in").read_text()


@pytest.mark.parametrize("profile", ["gpu-l40s", "gpu-h200"])
def test_an_incomplete_gpu_lock_is_not_presented_as_complete(profile) -> None:
    lock = (ROOT / f"requirements/{profile}.lock").read_text()
    assert "NOT a resolved lock" in lock and "pending lock regeneration" in lock
    meta = yaml.safe_load((ROOT / "requirements/profiles.yaml").read_text())["profiles"][profile]
    assert meta["lock_status"] == "pending-regeneration"
    assert set(REQUIRED) <= set(meta["explicit_runtime_dependencies"])
    assert meta["validation_status"] == "cai-validation-pending"
