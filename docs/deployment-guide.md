# Deployment Guide

## Shared project

Create `bni-ai-training-shared` and deploy the Applications below. Each Application installs exactly one standalone dependency profile (`docs/dependency-profiles.md`); profiles are never layered. Runtime profiles (`local-macos`, `sandbox-l40s`, `bni-h200`) are described in `docs/runtime-profiles.md`. Use environment variables for secrets and environment-specific paths.

| Application | CAI Script | Dependency profile | Baseline |
|---|---|---|---|
| `bni-vllm-qwen35-9b` | `deployments/cai/vllm/app.py` | `gpu-l40s` or `gpu-h200` | 16 vCPU, 64 GB, 1 GPU |
| `bni-qdrant` | `deployments/cai/qdrant/app.py` | `rag` (the launcher itself needs only the standard library) | 4 vCPU, 16 GB |
| `bni-phoenix` | `deployments/cai/phoenix/app.py` | `observability` (Phoenix server only; no CrewAI) | 4 vCPU, 16 GB |
| `bni-litellm` | `deployments/cai/litellm/app.py` | `gateway` | 2 vCPU, 4 GB |

The Qdrant launcher needs an existing binary at `QDRANT_BINARY`; it never downloads one. Run
`bash scripts/prepare_qdrant_binary.sh` once from a Session (pinned release and SHA-256 in
`requirements/qdrant-binary-manifest.json`), then deploy the Application. A missing binary fails with a clear message.

The vLLM launcher (`deployments/cai/vllm/app.py`) reads `MODEL_PATH` (any existing NFS path; it fails before startup
if the directory has no `config.json` or `.safetensors` files and it never downloads or modifies the model),
`CDSW_APP_PORT` (the platform port; 8101 only as a Session fallback, never hard-code a port), `VLLM_HOST` (default
`0.0.0.0`), `VLLM_MODEL` or `SERVED_MODEL_NAME` (default `qwen3.5-9b`), `VLLM_DTYPE`, `MAX_MODEL_LEN` and
`GPU_MEMORY_UTILIZATION` (L40S validated: bfloat16, 8192, 0.82). Without `nvcc` it sets
`VLLM_USE_FLASHINFER_SAMPLER=0` unless you set it explicitly. Application deployment itself is
`cai-validation-pending`. The vLLM model is loaded from `MODEL_PATH` on NFS. Keep tensor parallel size one. For each group project, select `deployments/cai/streamlit/app.py` using 1 vCPU and 2 GB.

The global limit is five active Applications. For the Day 1 final UI exercise, keep vLLM and Qdrant active and rotate group Applications in four waves: groups 01-03, 04-06, 07-09, and 10. Stop the active group wave before starting Phoenix. Start LiteLLM only for the Day 2 gateway module.

API v2 automation defaults to plan-only mode. Compare the generated request fields with the target `/api/v2/swagger.html` before adding `--execute`. The exact runtime identifier must come from the target CAI runtime catalog.

Step-by-step creation of the five shared Applications, with the exact environment variables, is in
`docs/trainer/cai-application-deployment.md`. The older per-environment dry-run pages were folded into it.
