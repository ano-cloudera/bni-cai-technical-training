#!/usr/bin/env bash
set -euo pipefail
mode="${1:---fixture-mode}"
if [[ "$mode" != "--fixture-mode" ]]; then echo "Only --fixture-mode is allowed without explicit live operator confirmation" >&2; exit 2; fi
mkdir -p build
cli=(python -m automation.cai_api_v2.cli --config config/env.local.example.yaml)
# Default topology: single_project (no WORKSHOP_TOPOLOGY set).
env -u WORKSHOP_TOPOLOGY PYTHONPATH=src:. "${cli[@]}" plan --output build/cai-plan.json
python -m json.tool build/cai-plan.json >/dev/null
python - <<'PY'
import json
plan = json.load(open("build/cai-plan.json"))
assert plan["topology"] == "single_project" and plan["project_count"] == 1, plan["topology"]
PY
# Explicit multi_project keeps the rc1 plan.
env -u WORKSHOP_TOPOLOGY PYTHONPATH=src:. "${cli[@]}" --topology multi_project plan --output build/cai-plan-multi.json
python - <<'PY'
import json
plan = json.load(open("build/cai-plan-multi.json"))
assert len(plan["projects"]) == 11 and len(plan["group_application_waves"]) == 4
PY
echo "Dry-run plans verified (default single_project, explicit multi_project). No API writes were made."
