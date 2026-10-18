from __future__ import annotations

import json
import platform
import subprocess
from typing import Mapping


def collect_environment() -> dict[str, str]:
    values = {"python": platform.python_version(), "platform": platform.platform()}
    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.splitlines()[0]
        values["gpu_name"], values["driver"] = [x.strip() for x in output.split(",", 1)]
    except Exception:
        values["gpu_name"] = "not-detected"
    try:
        import torch

        values.update(
            torch=str(torch.__version__),
            cuda_runtime=str(torch.version.cuda),
            cuda_available=str(torch.cuda.is_available()),
        )
    except ImportError:
        values["torch"] = "not-installed"
    return values


def build_report(values: Mapping[str, str]) -> dict:
    python_version = values.get("python", "0")
    gpu = values.get("gpu_name", "")
    return {
        **values,
        "python_compatible": python_version.startswith("3.10."),
        "gpu_compatible": "H200" in gpu or "H100" in gpu or "L40" in gpu,
        "decision": "validate_gpu_matrix" if "cuda_runtime" not in values else "ready_for_profile_check",
    }


def main() -> int:
    print(json.dumps(build_report(collect_environment()), indent=2, sort_keys=True))
    return 0
