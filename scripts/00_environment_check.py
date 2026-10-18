from __future__ import annotations

import sys

from bni_training.environment import build_report, collect_environment
from bni_training.labs import run_lab
from bni_training.runtime_profiles import active_profile_name, load_profile, missing_env

DESCRIPTION = "Lab 00: validate Python, GPU visibility, CUDA runtime, and the selected runtime profile."


def body(args, report):
    values = collect_environment()
    summary = build_report(values)
    report.data["environment"] = summary
    cai = args.mode == "cai"

    major_minor = ".".join(values["python"].split(".")[:2])
    if major_minor == "3.10":
        report.passed("python", values["python"])
    elif not cai and major_minor in {"3.11", "3.12"}:
        report.passed("python", f"{values['python']} (local mode accepts 3.10-3.12; CAI requires 3.10)")
    else:
        report.failed("python", f"{values['python']} is not supported; use the PBJ Python 3.10 runtime")

    gpu_found = values.get("gpu_name", "not-detected") != "not-detected"
    if gpu_found:
        (report.passed if summary["gpu_compatible"] else report.failed)("gpu", values["gpu_name"])
    elif cai:
        report.failed(
            "gpu", "No NVIDIA GPU detected. Use the NVIDIA GPU PBJ runtime and GPU resource profile"
        )
    else:
        report.skipped("gpu", "No NVIDIA GPU in local mode (expected on macOS)")

    if values.get("cuda_available") == "True":
        report.passed("cuda_runtime", f"torch {values['torch']} CUDA {values['cuda_runtime']}")
    elif cai:
        report.failed(
            "cuda_runtime", f"torch={values.get('torch')} cuda_available={values.get('cuda_available')}"
        )
    else:
        report.skipped("cuda_runtime", "CUDA is not available in local mode (expected on macOS)")

    name = active_profile_name()
    if name is None:
        if cai:
            report.failed("runtime_profile", "Set RUNTIME_PROFILE to sandbox-l40s or bni-h200")
        else:
            report.skipped("runtime_profile", "RUNTIME_PROFILE is not set")
    else:
        profile = load_profile(name)
        missing = missing_env(profile, "participant")
        if missing:
            report.failed("runtime_profile", f"{name}: missing environment variables {missing}")
        else:
            report.passed("runtime_profile", name)


def main(argv=None) -> int:
    return run_lab("00", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
