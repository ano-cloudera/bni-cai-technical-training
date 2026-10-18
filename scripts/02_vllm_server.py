from __future__ import annotations

import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

from bni_training.labs import PrerequisiteMissing, run_lab
from deployments.cai.vllm.app import GPU_PROFILES, build_command

DESCRIPTION = "Lab 02: preview the trainer-led single-GPU vLLM Application command (TP=1, BF16)."


def check_command(command: list[str], report, expected_profile: str) -> None:
    flags = {command[i]: command[i + 1] for i in range(len(command) - 1) if command[i].startswith("--")}
    problems = []
    if flags.get("--tensor-parallel-size") != "1":
        problems.append("tensor-parallel-size must be 1")
    if flags.get("--dtype") != "bfloat16":
        problems.append("dtype must be bfloat16")
    if flags.get("--host") != "127.0.0.1":
        problems.append("host must be 127.0.0.1 for a CAI Application")
    if flags.get("--gpu-memory-utilization") != GPU_PROFILES[expected_profile]["gpu_memory_utilization"]:
        problems.append("gpu-memory-utilization does not match the GPU profile")
    (report.failed if problems else report.passed)("vllm_command", "; ".join(problems) or shlex.join(command))


def body(args, report):
    if args.mode == "local":
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp)
            (model / "config.json").write_text("{}")
            (model / "model.safetensors").write_bytes(b"x")
            for profile in GPU_PROFILES:
                env = {"MODEL_PATH": str(model), "CDSW_APP_PORT": "8080", "GPU_PROFILE": profile}
                check_command(build_command(env), report, profile)
        report.skipped(
            "vllm_server_start", "Starting vLLM needs an NVIDIA GPU and the NFS model (not available locally)"
        )
        return
    env = dict(os.environ)
    if not env.get("MODEL_PATH") or not env.get("GPU_PROFILE"):
        raise PrerequisiteMissing("Set MODEL_PATH, GPU_PROFILE and CDSW_APP_PORT")
    command = build_command(env)
    check_command(command, report, env["GPU_PROFILE"].lower())
    if env.get("TRAINER_EXECUTE_VLLM", "").lower() == "true":
        code = subprocess.call(command)
        (report.passed if code == 0 else report.failed)("vllm_server_start", f"exit code {code}")
    else:
        report.skipped(
            "vllm_server_start",
            "Preview only. The trainer starts the Application; set TRAINER_EXECUTE_VLLM=true to run it here",
        )


def main(argv=None) -> int:
    return run_lab("02", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
