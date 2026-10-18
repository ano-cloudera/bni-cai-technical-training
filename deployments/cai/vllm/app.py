from __future__ import annotations

import os
from collections.abc import Mapping

from bni_training.model_artifact import validate_model_path
from deployments.cai.common import http_ready, resolve_cai_port, run_supervised

GPU_PROFILES = {
    "l40s": {"gpu_memory_utilization": "0.82", "max_model_len": "8192", "max_num_seqs": "16"},
    "h200": {"gpu_memory_utilization": "0.75", "max_model_len": "8192", "max_num_seqs": "32"},
}


def build_command(env: Mapping[str, str]) -> list[str]:
    model = validate_model_path(env.get("MODEL_PATH", ""))
    profile_name = env.get("GPU_PROFILE", "h200").lower()
    if profile_name not in GPU_PROFILES:
        raise ValueError(f"GPU_PROFILE must be one of {sorted(GPU_PROFILES)}")
    profile = GPU_PROFILES[profile_name]
    port = resolve_cai_port(env)
    command = [
        env.get("PYTHON_EXECUTABLE", "python"),
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model",
        str(model),
        "--served-model-name",
        env.get("SERVED_MODEL_NAME", "qwen3.5-9b"),
        "--host",
        "127.0.0.1",
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
    if env.get("VLLM_CHAT_TEMPLATE"):
        command.extend(["--chat-template", env["VLLM_CHAT_TEMPLATE"]])
    if env.get("SERVICE_AUTH_MODE") == "bearer" and env.get("VLLM_API_KEY"):
        command.extend(["--api-key", env["VLLM_API_KEY"]])
    return command


def main() -> int:
    env = dict(os.environ)
    port = resolve_cai_port(env)
    timeout = float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "15")) * 60
    return run_supervised(
        build_command(env),
        env=env,
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/health"),
        startup_timeout=timeout,
    )


if __name__ == "__main__":
    raise SystemExit(main())
