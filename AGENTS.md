# Codex Working Agreement

Use Python 3.10-compatible syntax and keep all code, notebooks, and documentation in English. Read `PROJECT_STATE.md` before changing behavior and update it after every validated milestone.

Preserve these invariants:

- Fully synthetic data only. The rc1 dataset in `data/csv` is kept for the legacy topology; labs, notebook templates and the Portal use `data/raw`.
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
- `config/workshop/labs.yaml` is the registry of the 13 labs and notebook templates (`notebooks/templates/`); never rely on file name order. Labs 03-12 use the one shared vLLM endpoint. Participants never start vLLM and never download the model: labs 01 and 02 are trainer-only. Every participant lab resolves `GROUP_ID`, `DATASET_ID`, `MISSION_ID` and `GROUP_WORKSPACE`, supports `--mode local|cai`, and `cai` mode never mocks silently.
- Group workspaces under `workshop/runtime/` are generated and git-ignored, hold no secrets in `group.env`, never copy the dataset, and are managed only by the seven workspace scripts (dry run by default). Notebooks are committed stripped.
- `plan` defaults to `single_project`; `multi_project` is explicit and an unknown `WORKSHOP_TOPOLOGY` fails. Tracked files must contain no real local path (`python scripts/audit_local_paths.py`).
- CSV is the default participant backend (`DATA_BACKEND=csv`). Impala is an optional trainer-controlled extension and is never required for the participant workflow.
- Impala GSSAPI, Impala LDAP, and CSV are explicit modes. Never silently fall back between backends, and never fall back after an authentication failure.
- Secrets come from environment variables and must never appear in commits, logs, traces, notebooks, or archives.
- Model weights remain on NFS and are never packaged.

Run `PYTHONPATH=src:. pytest -q`, `bash scripts/smoke_test.sh`, and local acceptance before packaging. Use the CAI API v2 CLI in dry-run mode until the target Swagger, runtime identifiers, and resource profiles are validated.

