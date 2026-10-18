#!/usr/bin/env bash
set -euo pipefail
version=""
while [[ $# -gt 0 ]]; do case "$1" in --version) version="$2"; shift 2;; *) echo "Unknown argument: $1" >&2; exit 2;; esac; done
[[ -n "$version" ]] || { echo "--version is required" >&2; exit 2; }
python scripts/acceptance_test.py --mode local --report build/acceptance-local.md
python scripts/secret_scan.py
PYTHONPATH=src:. python scripts/package_release.py --version "$version"

