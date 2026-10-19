# Trainer: project setup (single project)

Status: local validation only. Nothing here has been run on Cloudera AI; every CAI step is `cai-validation-pending`
(`config/cai-validation-pending.yaml`). No CAI readiness is claimed.

## 1. One project, one clean clone

Follow `docs/cai-workbench-clean-clone.md` for the runtime, clone and `.env` steps, using the `sandbox-l40s` or
`bni-h200` profile. The default topology is `single_project` (`bni-ai-training-workshop`).

## 2. Check the dataset

```bash
python scripts/validate_dataset.py          # expects 22/22 checks PASS
python scripts/generate_synthetic_data.py --preview
```

The dataset in `data/raw` is committed and deterministic (seed 20260630, reference date 2026-06-30). Regenerate only
if you change the generator; the validator compares bytes. The unusual patterns for Group 06 are produced
by the same generator but no flag column, answer list or manifest is written anywhere in the project. The validator
regenerates them in memory and checks that ordinary queries find them.

## 3. Dry-run the plan (no API call)

```bash
PYTHONPATH=src:. python -m automation.cai_api_v2.cli --config config/env.sandbox-l40s.example.yaml \
  plan --topology single_project --output build/cai-plan.json
```

Expect 1 project, 10 group workspaces, up to 10 Sessions, 5 shared Applications, no per-group Streamlit
Applications, and the unresolved CAI items. The runtime identifier is taken from the target catalog and is never
hard-coded; compare the request fields with the target Swagger before any live write.

## 4. Start the Workshop Portal (one process, one replica)

Create **one** Application from `deployments/cai/workshop-portal/app.py` (dependency profile `rag`, 4 vCPU and
8-16 GB as a starting point). Set **replicas to exactly 1**. The inference limit (`PORTAL_MAX_CONCURRENT_INFERENCE`,
default 3) is a process-local semaphore, so a second replica or process would multiply it. The Portal also refuses to
start while another instance's heartbeat is fresh (`runtime/shared/state/portal-instance.json`).

Environment (names only; values come from the project environment):
`PORTAL_MODE=cai`, `LITELLM_BASE_URL` or `VLLM_BASE_URL`, `LITELLM_API_KEY` / `VLLM_API_KEY`, `QDRANT_URL`,
`QDRANT_API_KEY`, `EMBEDDING_MODEL_PATH`, `PHOENIX_ENDPOINT`, optional `PORTAL_MAX_CONCURRENT_INFERENCE`,
`PORTAL_MAX_QUEUE_DEPTH`, `PORTAL_QUEUE_TIMEOUT_S`, `PORTAL_REQUEST_TIMEOUT_S`, `PORTAL_MAX_RETRIES`.
`DATA_BACKEND` stays `csv`; the Portal does not enable Impala.

To try it on a laptop: `PORTAL_MODE=local streamlit run apps/workshop-portal/app.py` (mock model, in-memory Qdrant;
the page says LOCAL MODE).

## 5. Not built yet

`prepare_group_workspaces.py`, `assign_participants.py`, `reset_group_workspace.py` and the other workspace scripts
from the plan are not implemented. The Portal creates each session's folders on demand.
