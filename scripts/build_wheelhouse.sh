#!/usr/bin/env bash
set -euo pipefail
profile=""; output="wheelhouse"
while [[ $# -gt 0 ]]; do case "$1" in --profile) profile="$2"; shift 2;; --output) output="$2"; shift 2;; *) echo "Unknown argument: $1" >&2; exit 2;; esac; done
[[ -n "$profile" ]] || { echo "--profile is required" >&2; exit 2; }
[[ "$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == "3.10" ]] || { echo "Build the wheelhouse with Python 3.10" >&2; exit 2; }
lock="$(PYTHONPATH=. python -c 'import sys; from scripts.bootstrap import profile_lock; print(profile_lock(sys.argv[1]))' "$profile")"
mkdir -p "$output"; python -m pip download --only-binary=:all: --dest "$output" --requirement "$lock"
python - "$output" "$profile" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]); files=[]
for p in sorted(root.glob('*.whl')): files.append({'filename':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size})
Path('requirements/offline-manifest.json').write_text(json.dumps({'profile':sys.argv[2],'python':'3.10','platform':'target-pbj-linux','files':files,'status':'built'},indent=2)+'\n')
PY

