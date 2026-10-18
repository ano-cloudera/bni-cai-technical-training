# Deployment Guide

## Shared project

Create `bni-ai-training-shared` and deploy the Applications below. Use environment variables for secrets and environment-specific paths.

| Application | CAI Script | Dependency profile | Baseline |
|---|---|---|---|
| `bni-vllm-qwen35-9b` | `deployments/cai/vllm/app.py` | `gpu-l40s` or `gpu-h200` | 16 vCPU, 64 GB, 1 GPU |
| `bni-qdrant` | `deployments/cai/qdrant/app.py` | `rag` | 4 vCPU, 16 GB |
| `bni-phoenix` | `deployments/cai/phoenix/app.py` | `observability` | 4 vCPU, 16 GB |
| `bni-litellm` | `deployments/cai/litellm/app.py` | `gateway` | 2 vCPU, 4 GB |

The vLLM model is loaded from `MODEL_PATH` on NFS. Keep tensor parallel size one. For each group project, select `deployments/cai/streamlit/app.py` using 1 vCPU and 2 GB.

The global limit is five active Applications. For the Day 1 final UI exercise, keep vLLM and Qdrant active and rotate group Applications in four waves: groups 01-03, 04-06, 07-09, and 10. Stop the active group wave before starting Phoenix. Start LiteLLM only for the Day 2 gateway module.

API v2 automation defaults to plan-only mode. Compare the generated request fields with the target `/api/v2/swagger.html` before adding `--execute`. The exact runtime identifier must come from the target CAI runtime catalog.

