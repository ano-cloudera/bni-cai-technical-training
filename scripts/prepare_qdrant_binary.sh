#!/usr/bin/env bash
# Prepare the pinned, checksum-verified Qdrant binary. Run once from a CAI Session (the Application cannot download).
# Usage: bash scripts/prepare_qdrant_binary.sh [destination]   (default: /home/cdsw/tools/qdrant/qdrant)
# The pinned asset is in requirements/qdrant-binary-manifest.json. Override with QDRANT_BINARY_URL and
# QDRANT_BINARY_SHA256 together (for example a customer mirror). QDRANT_FORCE=1 replaces an existing binary.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m bni_training.qdrant_binary "$@"
