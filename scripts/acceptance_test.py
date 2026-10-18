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
        {"name": "application_manifests", "passed": root.joinpath("deployments/cai/manifests/applications.yaml").is_file()},
        {"name": "dependency_profiles", "passed": root.joinpath("requirements/profiles.yaml").is_file()},
        {"name": "automation", "passed": root.joinpath("automation/cai_api_v2/cli.py").is_file()},
        {"name": "secret_scan", "passed": not scan_tree(root)},
        {"name": "model_weights_excluded", "passed": not any(root.rglob("*.safetensors"))},
    ]
    return {
        "status": "ready_for_cai_validation" if all(c["passed"] for c in checks) else "failed",
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
        f"# Acceptance Report\n\nStatus: `{result['status']}`\n",
        *[("- [x] " if c["passed"] else "- [ ] ") + c["name"] for c in result["checks"]],
    ]
    args.report.write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ready_for_cai_validation" else 1


if __name__ == "__main__":
    raise SystemExit(main())
