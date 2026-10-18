from __future__ import annotations

import re
from pathlib import Path

import yaml

from scripts.bootstrap import build_install_command


EXPECTED = {
    "participant",
    "rag",
    "observability",
    "gateway",
    "guardrails",
    "gpu-l40s",
    "gpu-h200",
    "dev-test",
}


def test_every_profile_has_input_and_lock_files() -> None:
    profiles = yaml.safe_load(Path("requirements/profiles.yaml").read_text())["profiles"]
    assert set(profiles) == EXPECTED
    for name, profile in profiles.items():
        assert Path(profile["input"]).is_file(), name
        assert Path(profile["lock"]).is_file(), name


def test_every_runtime_requirement_is_exactly_pinned() -> None:
    profiles = yaml.safe_load(Path("requirements/profiles.yaml").read_text())["profiles"]
    pattern = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[^]]+\])?==[^=<>~!]+$")
    for name, profile in profiles.items():
        lines = Path(profile["lock"]).read_text().splitlines()
        requirements = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
        assert requirements, name
        assert all(pattern.match(line) for line in requirements), (name, requirements)


def test_gpu_profiles_are_explicitly_environment_gated() -> None:
    profiles = yaml.safe_load(Path("requirements/profiles.yaml").read_text())["profiles"]
    assert profiles["gpu-l40s"]["validation_status"] == "sandbox-validation-required"
    assert profiles["gpu-h200"]["validation_status"] == "bni-validation-required"
    assert profiles["gpu-l40s"]["vllm_version"] == "0.29.0"
    assert profiles["gpu-h200"]["vllm_version"] == "0.29.0"


def test_bootstrap_builds_profile_specific_online_and_offline_commands() -> None:
    online = build_install_command("participant", offline=False)
    offline = build_install_command("gateway", offline=True)
    assert online[-2:] == ["--requirement", "requirements/participant.lock"]
    assert "--no-index" in offline
    assert offline[-2:] == ["--requirement", "requirements/gateway.lock"]
