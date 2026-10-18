from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from scripts.bootstrap import build_install_command

PROFILES = yaml.safe_load(Path("requirements/profiles.yaml").read_text())["profiles"]
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
GPU = {"gpu-l40s", "gpu-h200"}
NON_GPU = sorted(EXPECTED - GPU)
PIN = re.compile(r"^[A-Za-z0-9_.-]+(?:\[[^]]+\])?==[^=<>~!;\s]+(?:\s*;\s*.+)?$")


def requirement_lines(path: str) -> list[str]:
    lines = Path(path).read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def names(path: str) -> set[str]:
    return {
        re.split(r"[=<>~!\[; ]", line, maxsplit=1)[0].lower().replace("_", "-")
        for line in requirement_lines(path)
    }


def test_every_profile_has_input_and_lock_files() -> None:
    assert set(PROFILES) == EXPECTED
    for name, profile in PROFILES.items():
        assert Path(profile["input"]).is_file(), name
        assert Path(profile["lock"]).is_file(), name


def test_obsolete_layered_profiles_are_gone() -> None:
    for obsolete in ("base", "rag-profile", "gpu"):
        assert not Path(f"requirements/{obsolete}.in").exists()
        assert not Path(f"requirements/{obsolete}.lock").exists()


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_every_runtime_requirement_is_exactly_pinned(name: str) -> None:
    requirements = requirement_lines(PROFILES[name]["lock"])
    assert requirements, name
    assert all(PIN.match(line) for line in requirements), (
        name,
        [line for line in requirements if not PIN.match(line)],
    )


@pytest.mark.parametrize("name", NON_GPU)
def test_non_gpu_locks_are_fully_resolved_standalone_files(name: str) -> None:
    text = Path(PROFILES[name]["lock"]).read_text()
    assert "uv pip compile" in text.splitlines()[1], "lock must record the compile command"
    if name != "observability":  # the Phoenix server is deliberately unconstrained by lab pins
        assert "-c requirements/constraints.txt" in text
    assert "--universal" in text and "--python-version 3.10" in text
    assert not re.search(r"^-[rc]\s", text, re.M), "a lock must not reference other files"
    assert len(requirement_lines(PROFILES[name]["lock"])) > 20


def test_gateway_and_guardrails_do_not_pull_in_other_application_stacks() -> None:
    for name in ("gateway", "guardrails"):
        locked = names(PROFILES[name]["lock"])
        assert not locked & {"crewai", "arize-phoenix", "qdrant-client", "streamlit", "vllm", "torch"}, name
    assert "litellm" in names(PROFILES["gateway"]["lock"])
    assert {"uvicorn", "fastapi"} <= names(PROFILES["gateway"]["lock"]), "litellm[proxy] extra is required"


def test_composed_profiles_contain_everything_they_include() -> None:
    participant = names(PROFILES["participant"]["lock"])
    for name in ("rag", "dev-test"):
        assert participant <= names(PROFILES[name]["lock"]), name
    assert {"qdrant-client", "sentence-transformers"} <= names(PROFILES["rag"]["lock"])
    assert {"pytest", "ruff", "nbclient", "ipykernel", "qdrant-client", "arize-phoenix"} <= names(
        PROFILES["dev-test"]["lock"]
    )
    assert PROFILES["rag"]["includes"] == ["participant"]
    assert "includes" not in PROFILES["observability"]


def test_phoenix_server_profile_is_isolated_from_crewai_and_participant_libraries() -> None:
    locked = names(PROFILES["observability"]["lock"])
    assert "arize-phoenix" in locked
    forbidden = {"crewai", "openai", "litellm", "qdrant-client", "streamlit", "impyla"}
    forbidden |= {"sentence-transformers"}
    assert not locked & forbidden, locked & forbidden
    source = "\n".join(requirement_lines(PROFILES["observability"]["input"]))
    assert "-r " not in source and "crewai" not in source.lower()
    header = Path(PROFILES["observability"]["lock"]).read_text().splitlines()[1]
    assert "constraints.txt" not in header, "the Phoenix server must not be constrained by shared lab pins"


def test_participant_profile_has_only_trace_client_dependencies_not_the_server() -> None:
    locked = names(PROFILES["participant"]["lock"])
    assert {
        "opentelemetry-sdk",
        "opentelemetry-exporter-otlp-proto-http",
        "openinference-instrumentation-crewai",
        "openinference-instrumentation-openai",
    } <= locked
    assert not locked & {"arize-phoenix", "arize-phoenix-evals", "strawberry-graphql", "arize-phoenix-client"}


def test_only_gpu_profiles_install_vllm() -> None:
    for name in NON_GPU:
        assert "vllm" not in names(PROFILES[name]["lock"]), name
    for name in GPU:
        assert "vllm" in names(PROFILES[name]["lock"])


def test_shared_constraints_are_minimal_and_applied_everywhere() -> None:
    constraint_lines = requirement_lines("requirements/constraints.txt")
    pinned = {line.split("==")[0].lower(): line.split("==")[1] for line in constraint_lines if "==" in line}
    assert set(pinned) == {"crewai", "openai", "pydantic", "pyyaml", "httpx"}
    for name in sorted(set(NON_GPU) - {"observability"}):
        for line in requirement_lines(PROFILES[name]["lock"]):
            package, _, version = line.partition("==")
            if package.lower() in pinned:
                assert version.split(" ")[0] == pinned[package.lower()], (name, line)


def test_known_incompatible_transitive_versions_stay_excluded() -> None:
    observability = {
        line.split("==")[0]: line for line in requirement_lines(PROFILES["observability"]["lock"])
    }
    assert observability["arize-phoenix-evals"].startswith("arize-phoenix-evals==2."), (
        "phoenix 12 needs evals 2.x"
    )
    assert observability["graphql-core"].startswith("graphql-core==3.2."), "strawberry needs graphql-core 3.2"
    assert observability["arize-phoenix"].startswith("arize-phoenix==12.")


@pytest.mark.parametrize("name", sorted(GPU))
def test_gpu_profiles_are_pending_and_carry_compatibility_metadata(name: str) -> None:
    profile = PROFILES[name]
    assert profile["validation_status"] == "cai-validation-pending"
    assert profile["cai_validation"] == "pending"
    assert profile["local_validation"] == "not-applicable-on-macos"
    assert profile["vllm_version"] == "0.29.0"
    compat = profile["compatibility"]
    assert {"vllm", "torch", "transformers", "cuda_wheel_family", "confirmed_by"} <= set(compat)
    assert "Lab 00" in compat["confirmed_by"]
    assert "PENDING" in Path(profile["lock"]).read_text().upper()
    assert PROFILES["gpu-l40s"]["gpu"] == "NVIDIA L40S" and PROFILES["gpu-h200"]["gpu"] == "NVIDIA H200 NVL"


def test_gpu_compatibility_file_is_pending_for_both_gpus() -> None:
    data = yaml.safe_load(Path("requirements/compatibility-profiles.yaml").read_text())["profiles"]
    assert {v["environment"] for v in data.values()} == {"sandbox-l40s", "bni-h200"}
    for entry in data.values():
        assert entry["status"] == "cai-validation-pending"
        assert entry["intended"]["vllm"] == "0.29.0"


def test_no_non_gpu_profile_claims_cai_validation() -> None:
    for name in NON_GPU:
        assert PROFILES[name]["cai_validation"] in {"pending", "not-applicable"}, name


def test_bootstrap_builds_profile_specific_online_and_offline_commands() -> None:
    online = build_install_command("participant", offline=False)
    offline = build_install_command("gateway", offline=True)
    assert online[-2:] == ["--requirement", "requirements/participant.lock"]
    assert "--no-index" in offline
    assert offline[-2:] == ["--requirement", "requirements/gateway.lock"]


def test_participant_keeps_wrapt_one_x_for_the_openinference_instrumentors() -> None:
    wrapt = next(
        line for line in requirement_lines(PROFILES["participant"]["lock"]) if line.startswith("wrapt==")
    )
    assert wrapt.startswith("wrapt==1."), "wrapt 2.x breaks openinference-instrumentation-crewai 0.1.x"
