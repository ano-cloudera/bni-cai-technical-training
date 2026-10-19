# Workshop Portal

One shared Streamlit Application for all ten groups (about 40 concurrent browsers). Entry point:
`apps/workshop-portal/app.py`; CAI launcher: `deployments/cai/workshop-portal/app.py`; logic:
`src/bni_training/workshop/portal/`.

- Each browser session selects a group (validated against `config/workshop/groups.yaml`) and receives a fresh
  `session_id`. Chat, dataset and scenario selection, outputs, temporary files, Qdrant filters and telemetry are
  keyed by `group_id` and `session_id`. There are no mutable module-level variables for user or group state.
- All LLM calls go to LiteLLM (when `LITELLM_BASE_URL` is set) or vLLM, through one shared inference gate:
  `PORTAL_MAX_CONCURRENT_INFERENCE` (default 3), `PORTAL_MAX_QUEUE_DEPTH` (60), `PORTAL_QUEUE_TIMEOUT_S` (120),
  `PORTAL_REQUEST_TIMEOUT_S` (60), `PORTAL_MAX_RETRIES` (2), `PORTAL_RETRY_BACKOFF_S` (1.0).
- `PORTAL_MODE=cai` (default) never uses a mock. `PORTAL_MODE=local` starts an in-process mock LLM and an
  in-memory Qdrant, and the UI says so.
- Sizing: 4 vCPU and 8 to 16 GB RAM as a starting point (see `config/workshop/applications.yaml`). Unmeasured; CAI
  sandbox validation pending.
- **One process, one replica.** The inference semaphore is process-local, so run exactly one Streamlit process and
  one CAI Application replica. A second instance refuses to start while the first one's heartbeat is fresh
  (`PORTAL_ENFORCE_SINGLE_INSTANCE`, default on). Verify the replica setting in CAI.
- **Group lock.** After the first chat or workflow action the group selector is disabled. Use *Reset session*
  (explicit confirmation) to clear all session state, outputs and temp files and choose again.
- The rc1 dataset in `data/csv` is only a temporary placeholder until the `data/raw` dataset slice lands.
- Isolation is operational, not a security boundary.

Dependency profile: `rag` (includes `participant`).
