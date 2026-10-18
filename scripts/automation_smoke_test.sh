#!/usr/bin/env bash
set -euo pipefail
mode="${1:---fixture-mode}"
if [[ "$mode" != "--fixture-mode" ]]; then echo "Only --fixture-mode is allowed without explicit live operator confirmation" >&2; exit 2; fi
PYTHONPATH=src:. python -m automation.cai_api_v2.cli --config config/env.local.example.yaml plan --output build/cai-plan.json
python -m json.tool build/cai-plan.json >/dev/null
echo "Dry-run plan verified. No API writes were made."

