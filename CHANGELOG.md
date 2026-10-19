# Changelog

## Unreleased (fix/cai-vllm-runtime-validation)

- CAI sandbox L40S findings applied: GPU inputs declare PyYAML, packaging, requests, certifi, urllib3, cachetools
  and cloudpickle (locks pending regeneration); the vLLM Application launcher validates `MODEL_PATH`, never
  downloads, uses `CDSW_APP_PORT` (fallback 8101), `VLLM_HOST`, `VLLM_MODEL` and turns the FlashInfer sampler off
  without `nvcc`; Qwen3.5 workshop requests disable thinking; generated `group.env` carries `LAB_MODE`,
  `GROUP_WORKSPACE`, `VLLM_BASE_URL` and `VLLM_MODEL` (`--lab-mode`, `--vllm-base-url`).

## Unreleased (feature/single-project-csv-workshop)

- Deterministic synthetic banking dataset in `data/raw` (100 branches, 10,000 customers, about 19,000 accounts,
  about 100,000 transactions, 5,000 loans; 12 MB) with manifests, a validator (21 checks) and a standard-library
  generator; semantic layer in `semantic/` (dictionary, relationships, 18 metrics, business terms); guarded
  read-only CSV engine; ten logical group bundles and missions in `data/scenarios`.
- Portal: mission display, group lock after the first action with explicit session reset, single-process and
  single-replica enforcement, friendly refusals, spans with group_id, session.id, dataset_id and mission_id.
- Single-project dry-run plan; `single_project` is now the default of `plan`, `multi_project` is explicit
  (`--topology` or `WORKSHOP_TOPOLOGY`), an unknown value fails, and the rc1 apply/wave commands require
  `multi_project`.
- Ten-group workspace lifecycle: `prepare_group_workspaces`, `validate_group_workspaces`, `assign_participants`,
  `reset_group_workspace`, `check_group_isolation`, `check_shared_services`, `archive_group_outputs`; a generated,
  git-ignored `workshop/runtime/` hierarchy with a non-secret `group.env` per group. `group_driver` is the default;
  optional, capacity-pending `individual_learning` creates anonymous participant workspaces.
- Labs and notebooks 00-12 migrated to the synthetic banking dataset: a lab registry
  (`config/workshop/labs.yaml`), 13 cell-by-cell authoring sources and stripped generated templates,
  `--mode local|cai` on every lab, trainer-only labs
  01 and 02 (participants never start vLLM), rc1 script paths kept as thin wrappers.
- Anomaly answers removed: no flag column, no anomaly manifest and no incident IDs are tracked; the
  generator keeps them in memory and the validator regenerates them to prove Group 06 can find the patterns.
- Tracked-file local-path audit (`scripts/audit_local_paths.py`) that does not match its own source, and
  `scripts/validate_clean_clone.py` reporting an overall `CLEAN_CLONE` PASS or FAIL.
- Packaging includes `workshop/templates` and `notebooks/templates` and excludes `workshop/runtime` and `group.env`.

- Shared Workshop Portal (one Streamlit Application for all ten groups): group registry, safe group paths,
  per-session namespaced state, outputs and telemetry, a shared inference gate (default 3 concurrent requests,
  queue, timeout, retry, cancel, overload handling), Qdrant calls always filtered by `group_id`, a CAI launcher
  and `config/workshop/{groups,applications}.yaml`. rc1 multi-project mode is untouched.

## 0.1.0-dev - local hardening

- Qdrant group filter now uses native `qdrant-client` `Filter`/`FieldCondition` models (works in local mode and
  serializes to the same REST JSON); retrieval verifies every returned point belongs to the requested group.
- Dependency profiles redesigned: standalone fully resolved locks per profile, shared constraints only where needed,
  each non-GPU profile validated in its own temporary Python 3.10 venv (`scripts/validate_profiles.py`).
  Removed layered `base`, `rag-profile`, and `gpu` profiles. GPU profiles carry intended compatibility metadata and
  stay CAI validation pending.
- Labs 00-12 support `--mode local` and `--mode cai` with explicit PASS/SKIPPED/FAIL checks. Lab 07 indexes and
  retrieves through Qdrant, lab 08 runs a real CrewAI crew (explicit mock mode locally), lab 09 verifies OpenInference
  traces in a real Phoenix server. Lab 02 no longer imports a missing `apps.vllm` module.
- Fixed `CsvBackend` raising a SQLite thread error when CrewAI called the data tool from a worker thread.
- Added runtime profiles `local-macos`, `sandbox-l40s`, `bni-h200`; added `SERVICE_AUTH_MODE` to `.env.example`.
- Phoenix server profile isolated from CrewAI and participant libraries; trace clients moved to `participant`.
- Notebook stripper/checker (`scripts/strip_notebooks.py`); pending CAI validations registered in `config/cai-validation-pending.yaml`.
- Notebooks execute through `nbclient` and fail on errors, missing status, or unfinished cells.
- Acceptance status renamed `local_validation_passed`; CAI readiness is not claimed.

## 0.1.0-dev - 2026-10-12

- Added complete synthetic banking dataset and Credit Portfolio Insight use case.
- Added 13 paired Python and Jupyter labs.
- Added shared vLLM, Qdrant, Phoenix, and LiteLLM Application assets.
- Added group Streamlit Application and Agent Studio reference client.
- Added Cloudera AI API v2 dry-run automation and safe cleanup boundaries.
- Added local acceptance, secret scanning, and deterministic release packaging.

