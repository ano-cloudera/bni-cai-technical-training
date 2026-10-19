from __future__ import annotations

import os
import sys

from bni_training.data.backend import BackendConfigError, impala_status
from bni_training.data.validation import validate_dataset
from bni_training.environment import build_report, collect_environment
from bni_training.labs import run_lab, workshop_role
from bni_training.runtime_profiles import active_profile_name, load_profile, missing_env

DESCRIPTION = "Lab 00: validate Python, runtime, group configuration, dataset and service variables."


def configure(parser):
    parser.add_argument(
        "--expect-gpu", action="store_true", help="Trainer in the GPU runtime: require a visible GPU and CUDA"
    )


def body(args, report):
    cai, role = args.mode == "cai", workshop_role()
    values = collect_environment()
    summary = build_report(values)
    report.data["environment"] = {k: v for k, v in summary.items() if k != "platform"}

    major_minor = ".".join(values["python"].split(".")[:2])
    if major_minor == "3.10":
        report.passed("python", values["python"])
    elif not cai and major_minor in {"3.11", "3.12"}:
        report.passed("python", f"{values['python']} (local mode accepts 3.10-3.12; CAI requires 3.10)")
    else:
        report.failed("python", f"{values['python']} is not supported; use the PBJ Python 3.10 runtime")

    gpu_found = values.get("gpu_name", "not-detected") != "not-detected"
    if args.expect_gpu:
        (report.passed if gpu_found and summary["gpu_compatible"] else report.failed)(
            "gpu", values.get("gpu_name", "not-detected")
        )
        cuda_ok = values.get("cuda_available") == "True"
        (report.passed if cuda_ok else report.failed)("cuda_runtime", f"torch={values.get('torch')}")
    else:
        reason = "participant Sessions are CPU-only; the GPU belongs to the shared vLLM Application"
        report.skipped("gpu", reason if cai else "No NVIDIA GPU in local mode (expected on macOS)")
        report.skipped("cuda_runtime", "not expected without --expect-gpu (trainer, GPU runtime only)")

    name = active_profile_name()
    if name is None:
        report.skipped("runtime_profile", "RUNTIME_PROFILE is not set") if not cai else report.failed(
            "runtime_profile", "Set RUNTIME_PROFILE to sandbox-l40s or bni-h200"
        )
    else:
        missing = missing_env(load_profile(name), "participant")
        (report.failed if missing else report.passed)(
            "runtime_profile", f"{name}: missing {missing}" if missing else name
        )

    context = report.context
    if context is not None:
        report.passed("group_context", f"{context.group_id} / {context.dataset_id} / {context.mission_id}")
        report.passed("group_workspace", f"groups/{context.group_id} is writable")
    elif role == "trainer":
        report.skipped(
            "group_context", "trainer role: no group is needed (" + report.data.get("group_error", "") + ")"
        )
    else:
        report.failed(
            "group_context", report.data.get("group_error", "group configuration could not be resolved")
        )

    dataset = validate_dataset(check_determinism=False, check_missions=False)
    (report.passed if dataset.passed else report.failed)(
        "dataset", f"{len(dataset.checks)} structural checks" if dataset.passed else dataset.failures[0].name
    )

    if cai:
        required = "VLLM_BASE_URL"
        (report.passed if os.getenv(required) else report.failed)(
            "shared_model_endpoint", f"{required} is set" if os.getenv(required) else f"{required} is not set"
        )
    else:
        report.skipped("shared_model_endpoint", "Local mode uses an in-process mock model")
    for variable, lab in (
        ("QDRANT_URL", "07"),
        ("PHOENIX_COLLECTOR_ENDPOINT", "09"),
        ("PHOENIX_UI_URL", "09"),
        ("LITELLM_BASE_URL", "10"),
        ("WORKSHOP_PORTAL_URL", "12"),
    ):
        if os.getenv(variable):
            report.passed(f"service_{variable.lower()}", "set")
        else:
            report.skipped(
                f"service_{variable.lower()}",
                f"not set; needed from lab {lab} (depends on the workshop phase)",
            )
    try:
        status, detail = impala_status()
        report.skipped("impala", detail) if status == "SKIPPED" else report.passed("impala", detail)
    except BackendConfigError as exc:
        report.failed("impala", str(exc))


def main(argv=None) -> int:
    return run_lab("00", DESCRIPTION, body, argv, configure, participant="optional")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
