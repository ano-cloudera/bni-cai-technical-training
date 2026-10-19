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
    command = vllm_command(
        {"MODEL_PATH": str(tmp_path), "CDSW_APP_PORT": "8080", "GPU_PROFILE": "l40s"}
    )
    assert command[:3] == ["python", "-m", "vllm.entrypoints.openai.api_server"]
    assert command[command.index("--tensor-parallel-size") + 1] == "1"
    assert command[command.index("--gpu-memory-utilization") + 1] == "0.82"
    assert command[command.index("--max-model-len") + 1] == "8192"
    assert command[command.index("--host") + 1] == "0.0.0.0"  # configurable via VLLM_HOST


def test_vllm_h200_command_uses_validated_baseline(tmp_path: Path) -> None:
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"x")
    command = vllm_command(
        {"MODEL_PATH": str(tmp_path), "CDSW_APP_PORT": "8080", "GPU_PROFILE": "h200"}
    )
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
    assert phoenix_command(env)[-1] == "8123"
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
