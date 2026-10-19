# Codex Working Agreement

Use Python 3.10-compatible syntax and keep all code, notebooks, and documentation in English. Read `PROJECT_STATE.md` before changing behavior and update it after every validated milestone.

Preserve these invariants:

- Fully synthetic data only. The rc1 dataset in `data/csv` is a temporary placeholder; the dataset in `data/raw` replaces it for the single-project topology.
- Ten group IDs, `group_01` through `group_10`.
- One shared Qwen3.5-9B vLLM endpoint on one H200, BF16, TP=1.
- One shared Qdrant collection with a mandatory `group_id` filter.
- One shared Phoenix and one shared LiteLLM Application.
- Default topology `WORKSHOP_TOPOLOGY=single_project`: one CAI Project, ten group workspaces, and ONE shared Streamlit Workshop Portal Application for all groups. There are no per-group Streamlit Applications in this topology.
- The Workshop Portal runs as exactly one Streamlit process and one CAI Application replica, because its inference concurrency limit (default 3) is process-local. Never scale it out.
- No more than five CAI Applications are active at any time in total (vLLM, Qdrant, Phoenix, LiteLLM, Workshop Portal; LiteLLM and Phoenix by phase).
- Optional legacy topology `WORKSHOP_TOPOLOGY=multi_project` (one shared project plus ten group projects, with at most five group Streamlit Applications active, three during the Day 1 rotation) is preserved and must keep working.
- Group separation is operational (application-layer validation), not a security boundary. A session is locked to its group after its first chat or workflow action; changing group requires an explicit session reset.
- One physical synthetic dataset in `data/raw` serves ten logical group bundles in `data/scenarios`; never copy the data per group. Participant tools are read-only, limited to the group's tables and metrics, and no anomaly flag, answer key or manifest is ever committed, written to disk or shown.
- CSV is the default participant backend (`DATA_BACKEND=csv`). Impala is an optional trainer-controlled extension and is never required for the participant workflow.
- Impala GSSAPI, Impala LDAP, and CSV are explicit modes. Never silently fall back between backends, and never fall back after an authentication failure.
- Secrets come from environment variables and must never appear in commits, logs, traces, notebooks, or archives.
- Model weights remain on NFS and are never packaged.

Run `PYTHONPATH=src:. pytest -q`, `bash scripts/smoke_test.sh`, and local acceptance before packaging. Use the CAI API v2 CLI in dry-run mode until the target Swagger, runtime identifiers, and resource profiles are validated.

