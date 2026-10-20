from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

from bni_training.model_artifact import validate_model_path
from deployments.cai.common import http_ready, resolve_cai_port, run_supervised

FALLBACK_PORT = 8101  # Session or local testing only; a CAI Application always gets CDSW_APP_PORT
DEFAULT_HOST = "127.0.0.1"  # CAI expects Applications on loopback; 0.0.0.0 gave "Address already in use"
DEFAULT_SERVED_MODEL = "qwen3.5-9b"
GPU_PROFILES = {
    "l40s": {"gpu_memory_utilization": "0.82", "max_model_len": "8192", "max_num_seqs": "16"},
    "h200": {"gpu_memory_utilization": "0.75", "max_model_len": "8192", "max_num_seqs": "32"},
}


def resolve_port(env: Mapping[str, str]) -> int:
    """CDSW_APP_PORT on CAI; 8101 only when it is not set. An invalid CDSW_APP_PORT is an error."""
    if not env.get("CDSW_APP_PORT", "").strip():
        return FALLBACK_PORT
    return resolve_cai_port({"CDSW_APP_PORT": env["CDSW_APP_PORT"]})


def served_model_name(env: Mapping[str, str]) -> str:
    return env.get("VLLM_MODEL") or env.get("SERVED_MODEL_NAME") or DEFAULT_SERVED_MODEL


def cuda_toolkit_available(env: Mapping[str, str]) -> bool:
    """True when nvcc is found on PATH, in CUDA_HOME or in /usr/local/cuda. Nothing is installed."""
    search_path = env.get("PATH", os.environ.get("PATH", ""))
    if shutil.which("nvcc", path=search_path):
        return True
    roots = [env.get("CUDA_HOME", ""), "/usr/local/cuda"]
    return any(root and (Path(root) / "bin" / "nvcc").is_file() for root in roots)


def runtime_environment(env: Mapping[str, str]) -> dict[str, str]:
    """Child environment extras: FlashInfer sampler off without nvcc (explicit wins); no model download."""
    extra = {"HF_HUB_OFFLINE": env.get("HF_HUB_OFFLINE", "1")}
    if "VLLM_USE_FLASHINFER_SAMPLER" not in env and not cuda_toolkit_available(env):
        extra["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    return extra


def redacted(command: list[str]) -> list[str]:
    result, hide = [], False
    for part in command:
        result.append("***" if hide else part)
        hide = part == "--api-key"
    return result


def build_command(env: Mapping[str, str]) -> list[str]:
    model = validate_model_path(env.get("MODEL_PATH", ""))
    profile_name = env.get("GPU_PROFILE", "h200").lower()
    if profile_name not in GPU_PROFILES:
        raise ValueError(f"GPU_PROFILE must be one of {sorted(GPU_PROFILES)}")
    profile = GPU_PROFILES[profile_name]
    port = resolve_port(env)
    command = [
        env.get("PYTHON_EXECUTABLE", "python"),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(model),
        "--served-model-name",
        served_model_name(env),
        "--host",
        env.get("VLLM_HOST", DEFAULT_HOST),
        "--port",
        str(port),
        "--tensor-parallel-size",
        env.get("TENSOR_PARALLEL_SIZE", "1"),
        "--dtype",
        env.get("VLLM_DTYPE", "bfloat16"),
        "--max-model-len",
        env.get("MAX_MODEL_LEN", profile["max_model_len"]),
        "--gpu-memory-utilization",
        env.get("GPU_MEMORY_UTILIZATION", profile["gpu_memory_utilization"]),
        "--max-num-seqs",
        env.get("MAX_NUM_SEQS", profile["max_num_seqs"]),
    ]
    if env.get("VLLM_REASONING_PARSER"):
        command.extend(["--reasoning-parser", env["VLLM_REASONING_PARSER"]])
    if env.get("VLLM_TOOL_CALL_PARSER"):
        # CrewAI sends tool_choice="auto"; vLLM answers 400 unless both options are set.
        command.extend(["--enable-auto-tool-choice", "--tool-call-parser", env["VLLM_TOOL_CALL_PARSER"]])
    if env.get("VLLM_CHAT_TEMPLATE"):
        command.extend(["--chat-template", env["VLLM_CHAT_TEMPLATE"]])
    if env.get("SERVICE_AUTH_MODE") == "bearer" and env.get("VLLM_API_KEY"):
        command.extend(["--api-key", env["VLLM_API_KEY"]])
    return command


def main() -> int:
    env = dict(os.environ)
    command = build_command(
        env
    )  # fails clearly on a missing or incomplete MODEL_PATH, before anything starts
    extra = runtime_environment(env)
    port = resolve_port(env)
    settings = {
        "command": redacted(command),
        "port": port,
        "port_source": "CDSW_APP_PORT" if env.get("CDSW_APP_PORT", "").strip() else "fallback",
        "extra_environment": extra,
    }
    print("vLLM Application startup configuration: " + json.dumps(settings), file=sys.stderr, flush=True)
    timeout = float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "15")) * 60
    return run_supervised(
        command,
        env={**env, **extra},
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/health"),
        startup_timeout=timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
