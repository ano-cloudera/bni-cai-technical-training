"""Explicit runtime profiles: local-macos, sandbox-l40s, bni-h200.

A profile lists which environment variable NAMES are required and which checks are MANDATORY,
OPTIONAL, or SKIPPED. Values are never stored in the repository.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import yaml

PROFILE_DIR = Path(__file__).resolve().parents[2] / "config" / "profiles"
PROFILES = ("local-macos", "sandbox-l40s", "bni-h200")
POLICIES = {"MANDATORY", "OPTIONAL", "SKIPPED"}


def load_profile(name: str, directory: Path = PROFILE_DIR) -> dict:
    if name not in PROFILES:
        raise ValueError(f"RUNTIME_PROFILE must be one of {', '.join(PROFILES)}")
    data = yaml.safe_load((directory / f"{name}.yaml").read_text(encoding="utf-8"))
    bad = {k: v for k, v in data["checks"].items() if v not in POLICIES}
    if bad:
        raise ValueError(f"Unknown check policies in profile {name}: {bad}")
    return data


def active_profile_name(env: Mapping[str, str] | None = None) -> str | None:
    value = (os.environ if env is None else env).get("RUNTIME_PROFILE", "")
    return value or None


def missing_env(profile: Mapping, role: str, env: Mapping[str, str] | None = None) -> list[str]:
    source = os.environ if env is None else env
    return [name for name in profile["required_env"][role] if not source.get(name)]
