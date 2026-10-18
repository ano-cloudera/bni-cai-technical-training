from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bni_training.runtime_profiles import PROFILES, load_profile, missing_env

CHECKS = {
    "unit_tests",
    "lint",
    "profile_isolation",
    "local_smoke",
    "local_acceptance",
    "notebooks_local",
    "lab_environment_gpu",
    "cuda_torch",
    "vllm_serving",
    "nfs_model",
    "impala_live",
    "qdrant_server_live",
    "phoenix_server_live",
    "litellm_proxy_live",
    "cai_api_dry_run",
    "cai_api_live",
    "streamlit_waves",
    "ten_group_concurrency",
}


def test_three_explicit_profiles_exist() -> None:
    assert PROFILES == ("local-macos", "sandbox-l40s", "bni-h200")
    for name in PROFILES:
        profile = load_profile(name)
        assert profile["name"] == name
        assert set(profile["checks"]) == CHECKS


def test_local_macos_skips_everything_that_needs_gpu_cai_nfs_or_impala() -> None:
    checks = load_profile("local-macos")["checks"]
    for name in (
        "lab_environment_gpu",
        "cuda_torch",
        "vllm_serving",
        "nfs_model",
        "impala_live",
        "cai_api_live",
    ):
        assert checks[name] == "SKIPPED", name
    for name in ("unit_tests", "lint", "profile_isolation", "local_acceptance"):
        assert checks[name] == "MANDATORY", name


def test_gpu_checks_are_mandatory_in_cai_environments() -> None:
    for name in ("sandbox-l40s", "bni-h200"):
        checks = load_profile(name)["checks"]
        assert checks["vllm_serving"] == checks["cuda_torch"] == checks["nfs_model"] == "MANDATORY"
    assert load_profile("sandbox-l40s")["gpu_profile"] == "l40s"
    assert load_profile("bni-h200")["gpu_profile"] == "h200"
    assert load_profile("bni-h200")["checks"]["impala_live"] == "MANDATORY"


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="RUNTIME_PROFILE"):
        load_profile("laptop")


def test_missing_env_reports_names_only() -> None:
    profile = load_profile("sandbox-l40s")
    missing = missing_env(profile, "participant", {"GROUP_ID": "group_01"})
    assert "VLLM_BASE_URL" in missing and "GROUP_ID" not in missing


@pytest.mark.parametrize("name", PROFILES)
def test_env_examples_contain_no_secrets_hosts_or_runtime_ids(name: str) -> None:
    text = Path(f"config/profiles/{name}.env.example").read_text()
    assert f"RUNTIME_PROFILE={name}" in text
    for line in text.splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key.endswith(("API_KEY", "PASSWORD", "MASTER_KEY")):
            assert value in {"", "<set-at-runtime>"}, key
        if value.startswith("http"):
            assert ".invalid" in value, line
    assert "RUNTIME_IDENTIFIER" not in text.upper()


def test_profile_yaml_files_are_valid_yaml() -> None:
    for name in PROFILES:
        assert isinstance(yaml.safe_load(Path(f"config/profiles/{name}.yaml").read_text()), dict)
