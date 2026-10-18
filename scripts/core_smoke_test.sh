#!/usr/bin/env bash
set -euo pipefail
export GROUP_ID="${GROUP_ID:-group_01}"
export DATA_MODE="${DATA_MODE:-csv}"
export CSV_DATA_DIR="${CSV_DATA_DIR:-data/csv}"
export VLLM_BASE_URL="${VLLM_BASE_URL:-http://example.invalid/v1}"
export VLLM_API_KEY="${VLLM_API_KEY:-workshop-placeholder}"
PYTHONPATH=src:. python scripts/05_impala_ask_data.py >/dev/null
PYTHONPATH=src:. python scripts/06_semantic_layer.py >/dev/null
PYTHONPATH=src:. python scripts/08_multi_agent_workflow.py >/dev/null
echo "Core CSV smoke test passed."

