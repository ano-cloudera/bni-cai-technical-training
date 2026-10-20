"""Native vLLM Application startup: model path checks, port, host, FlashInfer and no download."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from deployments.cai.vllm import app

APP_SOURCE = Path(app.__file__).read_text()


def model_dir(tmp_path: Path, shards: bool = True) -> Path:
    path = tmp_path / "model"
    path.mkdir()
    (path / "config.json").write_text("{}")
    if shards:
        (path / "model-00001.safetensors").write_bytes(b"x")
    return path


def env_for(path: Path, **extra: str) -> dict[str, str]:
    return {"MODEL_PATH": str(path), "CDSW_APP_PORT": "8080", "GPU_PROFILE": "l40s", **extra}


def test_a_missing_model_path_setting_fails_clearly() -> None:
    with pytest.raises(ValueError, match="MODEL_PATH is not set"):
        app.build_command({"CDSW_APP_PORT": "8080"})


def test_a_model_directory_that_does_not_exist_fails_clearly(tmp_path) -> None:
    with pytest.raises(ValueError, match="MODEL_PATH is not a complete local model directory"):
        app.build_command(env_for(tmp_path / "absent"))


def test_an_incomplete_model_directory_fails_before_startup(tmp_path) -> None:
    with pytest.raises(ValueError, match="no .safetensors"):
        app.build_command(env_for(model_dir(tmp_path, shards=False)))
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="complete local model directory"):
        app.build_command(env_for(empty))


def test_any_model_path_is_accepted_and_the_model_is_not_modified(tmp_path) -> None:
    path = model_dir(tmp_path)
    before = sorted((p.name, p.stat().st_mtime_ns) for p in path.iterdir())
    command = app.build_command(env_for(path))
    assert command[command.index("--model") + 1] == str(path)
    assert sorted((p.name, p.stat().st_mtime_ns) for p in path.iterdir()) == before


def test_the_launcher_never_downloads_the_model() -> None:
    assert not re.search(
        r"snapshot_download|hf_hub_download|from_pretrained|huggingface-cli|urlretrieve", APP_SOURCE
    )
    assert app.runtime_environment({"PATH": ""})["HF_HUB_OFFLINE"] == "1"


def test_the_application_port_comes_from_cdsw_app_port(tmp_path) -> None:
    command = app.build_command(env_for(model_dir(tmp_path), CDSW_APP_PORT="9123"))
    assert command[command.index("--port") + 1] == "9123"


def test_the_fallback_port_is_8101_only_when_the_platform_port_is_absent(tmp_path) -> None:
    env = env_for(model_dir(tmp_path))
    del env["CDSW_APP_PORT"]
    assert app.resolve_port(env) == 8101 == app.FALLBACK_PORT
    with pytest.raises(ValueError, match="CAI Application port"):
        app.resolve_port({"CDSW_APP_PORT": "not-a-port"})


def test_port_8100_is_never_hard_coded() -> None:
    assert not re.search(r"\b8100\b", APP_SOURCE)


def test_host_and_served_model_name_are_configurable_with_defaults(tmp_path) -> None:
    path = model_dir(tmp_path)
    default = app.build_command(env_for(path))
    assert default[default.index("--host") + 1] == "127.0.0.1"
    assert default[default.index("--served-model-name") + 1] == "qwen3.5-9b"
    custom = app.build_command(env_for(path, VLLM_HOST="0.0.0.0", VLLM_MODEL="my-model"))
    assert custom[custom.index("--host") + 1] == "0.0.0.0"
    assert custom[custom.index("--served-model-name") + 1] == "my-model"
    legacy = app.build_command(env_for(path, SERVED_MODEL_NAME="legacy-name"))
    assert legacy[legacy.index("--served-model-name") + 1] == "legacy-name"


def test_l40s_defaults_match_the_validated_sandbox_settings(tmp_path) -> None:
    path = model_dir(tmp_path)
    command = app.build_command(env_for(path))
    assert command[command.index("--dtype") + 1] == "bfloat16"
    assert command[command.index("--max-model-len") + 1] == "8192"
    assert command[command.index("--gpu-memory-utilization") + 1] == "0.82"
    tuned = app.build_command(env_for(path, MAX_MODEL_LEN="4096", GPU_MEMORY_UTILIZATION="0.7"))
    assert tuned[tuned.index("--max-model-len") + 1] == "4096"
    assert tuned[tuned.index("--gpu-memory-utilization") + 1] == "0.7"


def test_flashinfer_sampler_is_disabled_when_nvcc_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app, "cuda_toolkit_available", lambda _env: False)
    assert app.runtime_environment({"PATH": ""})["VLLM_USE_FLASHINFER_SAMPLER"] == "0"


def test_nvcc_detection_finds_cuda_home_and_reports_absence(tmp_path) -> None:
    assert app.cuda_toolkit_available({"PATH": str(tmp_path), "CUDA_HOME": str(tmp_path / "missing")}) in (
        False,
        Path("/usr/local/cuda/bin/nvcc").is_file(),
    )


def test_flashinfer_default_is_kept_when_nvcc_exists(tmp_path) -> None:
    cuda = tmp_path / "cuda"
    (cuda / "bin").mkdir(parents=True)
    (cuda / "bin" / "nvcc").write_text("")
    assert "VLLM_USE_FLASHINFER_SAMPLER" not in app.runtime_environment({"PATH": "", "CUDA_HOME": str(cuda)})


def test_an_explicit_flashinfer_setting_is_respected(tmp_path) -> None:
    for value in ("1", "0"):
        extra = app.runtime_environment({"PATH": str(tmp_path), "VLLM_USE_FLASHINFER_SAMPLER": value})
        assert "VLLM_USE_FLASHINFER_SAMPLER" not in extra  # the child inherits the explicit value unchanged


def test_logged_command_never_contains_the_api_key(tmp_path) -> None:
    command = app.build_command(
        env_for(model_dir(tmp_path), SERVICE_AUTH_MODE="bearer", VLLM_API_KEY="s3cr3t-value")
    )
    assert "s3cr3t-value" in command
    assert "s3cr3t-value" not in " ".join(app.redacted(command))
