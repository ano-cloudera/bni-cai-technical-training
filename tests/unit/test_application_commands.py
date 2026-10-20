from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from deployments.cai.litellm.app import build_command as litellm_command
from deployments.cai.phoenix.app import build_command as phoenix_command
from deployments.cai.qdrant.app import build_command as qdrant_command
from deployments.cai.streamlit.app import build_command as streamlit_command
from deployments.cai.vllm.app import build_command as vllm_command


def test_vllm_l40s_command_uses_one_gpu_and_lower_utilization(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    command = vllm_command({"MODEL_PATH": str(tmp_path), "CDSW_APP_PORT": "8080", "GPU_PROFILE": "l40s"})
    assert command[:3] == ["python", "-m", "vllm.entrypoints.openai.api_server"]
    assert command[command.index("--tensor-parallel-size") + 1] == "1"
    assert command[command.index("--gpu-memory-utilization") + 1] == "0.82"
    assert command[command.index("--max-model-len") + 1] == "8192"
    assert command[command.index("--host") + 1] == "127.0.0.1"  # configurable via VLLM_HOST


def test_vllm_h200_command_uses_validated_baseline(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    command = vllm_command({"MODEL_PATH": str(tmp_path), "CDSW_APP_PORT": "8080", "GPU_PROFILE": "h200"})
    assert command[command.index("--gpu-memory-utilization") + 1] == "0.75"
    assert command[command.index("--dtype") + 1] == "bfloat16"


def test_vllm_rejects_unknown_gpu_profile(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    with pytest.raises(ValueError, match="GPU_PROFILE"):
        vllm_command({"MODEL_PATH": str(tmp_path), "CDSW_APP_PORT": "8080", "GPU_PROFILE": "a100"})


def test_service_commands_bind_to_cai_port() -> None:
    env = {"CDSW_APP_PORT": "8123", "QDRANT_BINARY": "/opt/qdrant", "LITELLM_CONFIG": "x.yaml"}
    assert qdrant_command(env) == ["/opt/qdrant"]
    assert phoenix_command(env)[-1] == "serve"  # host and port go through PHOENIX_HOST and PHOENIX_PORT
    assert litellm_command(env)[-1] == "8123"
    assert litellm_command(env)[0] == "litellm"
    assert streamlit_command(env)[-2:] == ["--server.address", "127.0.0.1"]
    assert "8123" in streamlit_command(env)


def test_manifests_use_python_entrypoints() -> None:
    payload = yaml.safe_load(Path("deployments/cai/manifests/applications.yaml").read_text())
    assert len(payload["applications"]) == 5
    for app in payload["applications"]:
        assert app["script"].endswith("/app.py")
        assert app["kernel"] == "python3"
        assert not app["script"].endswith(".sh")


def test_litellm_config_is_resolved_from_the_repository_not_the_working_directory(
    tmp_path, monkeypatch
) -> None:
    """A CAI Application starts in /home/cdsw; a relative config used to fail with 'Config file not found'."""
    from deployments.cai.common import REPO_ROOT
    from deployments.cai.litellm import app as litellm_app

    monkeypatch.chdir(tmp_path)
    command = litellm_command({"CDSW_APP_PORT": "8123"})
    assert command[command.index("--config") + 1] == str(REPO_ROOT / "config/litellm.yaml")
    assert Path(command[command.index("--config") + 1]).is_file()
    absolute = litellm_command({"CDSW_APP_PORT": "8123", "LITELLM_CONFIG": "/etc/other.yaml"})
    assert absolute[absolute.index("--config") + 1] == "/etc/other.yaml"
    assert litellm_app.resolve_config_path({}) == REPO_ROOT / "config/litellm.yaml"


def test_litellm_reports_config_variables_that_are_not_set(tmp_path) -> None:
    from deployments.cai.litellm import app as litellm_app

    config = tmp_path / "c.yaml"
    config.write_text(
        "a: os.environ/VLLM_BASE_URL\nb: os.environ/VLLM_API_KEY\nc: os.environ/MOCK_FALLBACK_BASE_URL\n"
    )
    missing = litellm_app.missing_config_variables(config, {"VLLM_BASE_URL": "https://x/v1"})
    assert missing == ["MOCK_FALLBACK_BASE_URL", "VLLM_API_KEY"]
    assert (
        litellm_app.missing_config_variables(
            config, {"VLLM_BASE_URL": "a", "VLLM_API_KEY": "b", "MOCK_FALLBACK_BASE_URL": "c"}
        )
        == []
    )
    real = litellm_app.missing_config_variables(litellm_app.resolve_config_path({}), {})
    assert {"VLLM_BASE_URL", "VLLM_API_KEY", "MOCK_FALLBACK_BASE_URL"} <= set(real)


def test_litellm_main_fails_clearly_when_the_config_is_missing(monkeypatch) -> None:
    from deployments.cai.litellm import app as litellm_app

    monkeypatch.setenv("CDSW_APP_PORT", "8123")
    monkeypatch.setenv("LITELLM_CONFIG", "/nonexistent/litellm.yaml")
    with pytest.raises(FileNotFoundError, match="LiteLLM config not found"):
        litellm_app.main()


def test_litellm_requires_a_master_key_and_explains_how_to_create_one(monkeypatch) -> None:
    from deployments.cai.litellm import app as litellm_app

    for env in ({}, {"LITELLM_MASTER_KEY": ""}, {"LITELLM_MASTER_KEY": "   "}):
        with pytest.raises(ValueError, match="LITELLM_MASTER_KEY is not set") as error:
            litellm_app.require_master_key(env)
        assert "secrets.token_hex" in str(error.value) and "never commit" in str(error.value)
    litellm_app.require_master_key({"LITELLM_MASTER_KEY": "sk-example"})
    monkeypatch.setenv("CDSW_APP_PORT", "8123")
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    with pytest.raises(ValueError, match="LITELLM_MASTER_KEY"):
        litellm_app.main()
