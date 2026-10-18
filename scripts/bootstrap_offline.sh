#!/usr/bin/env bash
set -euo pipefail
python scripts/bootstrap.py "${1:-participant}" --offline --wheelhouse wheelhouse

