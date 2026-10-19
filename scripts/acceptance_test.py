from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.secret_scan import scan_tree
except ModuleNotFoundError:
    from secret_scan import scan_tree


def local_checks(root: Path) -> dict:
    expected_scripts = [next(root.joinpath("scripts").glob(f"{i:02d}_*.py"), None) for i in range(13)]
    expected_notebooks = [next(root.joinpath("notebooks").glob(f"{i:02d}_*.ipynb"), None) for i in range(13)]
    checks = [
        {"name": "lab_scripts", "passed": all(expected_scripts)},
        {"name": "lab_notebooks", "passed": all(expected_notebooks)},
        {"name": "synthetic_manifest", "passed": root.joinpath("data/csv/manifest.json").is_file()},
        {
            "name": "python_cai_entrypoints",
            "passed": all(
                root.joinpath(f"deployments/cai/{name}/app.py").is_file()
                for name in ["vllm", "qdrant", "phoenix", "litellm", "streamlit"]
            ),
        },
        {
            "name": "application_manifests",
            "passed": root.joinpath("deployments/cai/manifests/applications.yaml").is_file(),
        },
        {"name": "dependency_profiles", "passed": root.joinpath("requirements/profiles.yaml").is_file()},
        {"name": "automation", "passed": root.joinpath("automation/cai_api_v2/cli.py").is_file()},
        {
            "name": "runtime_profiles",
            "passed": all(
                root.joinpath(f"config/profiles/{name}.yaml").is_file()
                and root.joinpath(f"config/profiles/{name}.env.example").is_file()
                for name in ["local-macos", "sandbox-l40s", "bni-h200"]
            ),
        },
        {
            "name": "profile_lock_files",
            "passed": all(
                root.joinpath(f"requirements/{name}.lock").is_file()
                for name in [
                    "participant",
                    "rag",
                    "observability",
                    "gateway",
                    "guardrails",
                    "dev-test",
                    "gpu-l40s",
                    "gpu-h200",
                ]
            ),
        },
        {
            "name": "labs_support_local_and_cai_modes",
            "passed": all(
                "run_lab(" in script.read_text()
                for script in root.joinpath("scripts").glob("[0-1][0-9]_*.py")
            ),
        },
        {
            "name": "cai_validation_pending_registered",
            "passed": root.joinpath("config/cai-validation-pending.yaml").is_file(),
        },
        {
            "name": "notebooks_stripped",
            "passed": all(
                not cell.get("outputs") and cell.get("execution_count") is None
                for notebook in root.joinpath("notebooks").glob("*.ipynb")
                for cell in json.loads(notebook.read_text())["cells"]
                if cell["cell_type"] == "code"
            ),
        },
        {
            "name": "synthetic_dataset_and_manifests",
            "passed": all(
                root.joinpath(f"data/raw/{name}.csv").is_file()
                for name in ["branches", "customers", "accounts", "transactions", "loans"]
            )
            and all(
                root.joinpath(f"data/manifests/{name}.json").is_file()
                for name in ["dataset_manifest", "checksums", "anomaly_test_manifest"]
            ),
        },
        {
            "name": "group_dataset_bundles",
            "passed": all(
                root.joinpath(f"data/scenarios/{name}.yaml").is_file()
                for name in ["dataset_bundles", "group_assignments", "sample_questions"]
            ),
        },
        {
            "name": "semantic_layer",
            "passed": all(
                root.joinpath(f"semantic/{name}").is_file()
                for name in [
                    "README.md",
                    "data_dictionary.yaml",
                    "relationships.yaml",
                    "metrics.yaml",
                    "business_terms.yaml",
                ]
            ),
        },
        {
            "name": "workshop_portal_entrypoint",
            "passed": root.joinpath("deployments/cai/workshop-portal/app.py").is_file()
            and root.joinpath("apps/workshop-portal/app.py").is_file(),
        },
        {"name": "no_env_file", "passed": not root.joinpath(".env").exists()},
        {"name": "secret_scan", "passed": not scan_tree(root)},
        {"name": "model_weights_excluded", "passed": not any(root.rglob("*.safetensors"))},
    ]
    return {
        "status": "local_validation_passed" if all(c["passed"] for c in checks) else "failed",
        "checks": checks,
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["local", "cai"], default="local")
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)
    if args.mode == "cai":
        raise SystemExit("CAI mode requires the operator-run checklist and is not implicit")
    result = local_checks(Path("."))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Acceptance Report\n\nStatus: `{result['status']}`\n\n"
        "CAI readiness: **not claimed**. GPU, CUDA, vLLM, NFS model, live Impala and live CAI API "
        "validation are pending.\n",
        *[("- [x] " if c["passed"] else "- [ ] ") + c["name"] for c in result["checks"]],
    ]
    args.report.write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "local_validation_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
