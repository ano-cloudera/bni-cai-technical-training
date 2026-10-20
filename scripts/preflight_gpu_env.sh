#!/usr/bin/env bash
# Read-only readiness check for a GPU Application environment (BNI H200 or the sandbox). It installs, downloads and
# changes nothing and prints no secrets. Run it from a Session on the GPU resource group, then stop that Session.
#
#   bash scripts/preflight_gpu_env.sh
#
# Optional settings (defaults for BNI): REPO, VENV, MODEL_PATH, EXPECT_GPU (substring, default H200),
# PREFLIGHT_SKIP_NETWORK=1 to skip the GitHub check.
set +e
REPO="${REPO:-/home/cdsw/bni-cai-technical-training}"
VENV="${VENV:-/home/cdsw/.venvs/bni-vllm-h200}"
MODEL_PATH="${MODEL_PATH:-/home/cdsw/models/Qwen3.5-9B}"
EXPECT_GPU="${EXPECT_GPU:-H200}"
check() { printf '%-7s %s\n' "$1" "$2"; }

echo "== 1. Repository"
if [ -d "$REPO/.git" ]; then
  git -C "$REPO" log --oneline -1
  if [ -n "$(git -C "$REPO" status --short | head -1)" ]; then check CHECK "the repository has local changes"; else check OK "clean working tree"; fi
else
  check CHECK "no git repository at $REPO (a zip copy is fine, but note the version)"
fi

echo "== 2. GPU and driver"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version --format=csv,noheader
  nvidia-smi --query-gpu=name --format=csv,noheader | grep -qi "$EXPECT_GPU" \
    && check OK "GPU name contains $EXPECT_GPU" || check CHECK "GPU name does not contain $EXPECT_GPU"
else
  check CHECK "nvidia-smi not found: this Session is not on a GPU resource group"
fi

echo "== 3. Python, torch, CUDA and vLLM ($VENV)"
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" - <<'PY'
import sys
print("python", sys.version.split()[0])
try:
    import torch
    print("torch", torch.__version__, "| cuda", torch.version.cuda, "| gpu available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        print(torch.cuda.get_device_name(0), "| capability", torch.cuda.get_device_capability(0),
              "| total GiB", round(total / 2**30, 1), "| free GiB", round(free / 2**30, 1))
except Exception as exc:
    print("CHECK torch:", exc)
try:
    import vllm
    print("vllm", vllm.__version__)
except Exception as exc:
    print("CHECK vllm:", exc)
for name in ("yaml", "requests", "packaging", "certifi", "urllib3", "cachetools", "cloudpickle"):
    try:
        __import__(name)
    except Exception:
        print("CHECK missing package:", name)
PY
  "$VENV/bin/python" -m pip check 2>&1 | tail -2
else
  check CHECK "no venv at $VENV (build it from requirements/gpu-*.in, see the deployment guide)"
fi

echo "== 4. Model files (nothing is downloaded)"
if [ -f "$MODEL_PATH/config.json" ]; then
  check OK "config.json found"
  echo "safetensors files: $(ls "$MODEL_PATH"/*.safetensors 2>/dev/null | wc -l)"
  du -sh "$MODEL_PATH" 2>/dev/null
else
  check CHECK "no config.json at $MODEL_PATH"
fi

echo "== 5. Other environments and folders"
for env in bni-rag bni-phoenix bni-litellm; do
  if [ -x "/home/cdsw/.venvs/$env/bin/python" ]; then
    printf '%s: ' "$env"; "/home/cdsw/.venvs/$env/bin/python" -V 2>&1
  else
    check CHECK "venv $env is missing"
  fi
done
for dir in /home/cdsw/bni-qdrant-storage /home/cdsw/bni-phoenix-data /home/cdsw/tools/qdrant; do
  if [ -d "$dir" ] && [ -w "$dir" ]; then check OK "$dir is writable"; else check CHECK "$dir is missing or not writable"; fi
done
if [ -x /home/cdsw/tools/qdrant/qdrant ]; then /home/cdsw/tools/qdrant/qdrant --version 2>&1 | head -1; else check CHECK "Qdrant binary not prepared"; fi
df -h /home/cdsw 2>/dev/null | tail -1

echo "== 6. Network (no credentials sent)"
if [ "${PREFLIGHT_SKIP_NETWORK:-0}" = "1" ]; then
  echo "skipped"
else
  curl -s -o /dev/null -m 10 -w "github.com -> HTTP %{http_code}\n" https://github.com
fi
echo "== done: lines marked CHECK need attention before creating the Applications"
exit 0
