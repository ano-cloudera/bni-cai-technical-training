# Changelog

## Unreleased (deployment guide update)

- `docs/trainer/cai-application-deployment.md`: vLLM Running in the sandbox on a small GPU (A10G settings and the
  KV cache error), the CPU and GPU resource groups, the Phoenix Starlette fix, wiring the Application URLs together,
  and the LiteLLM Admin UI limit (login needs a Postgres database; SQLite is not supported; an embedded Postgres was
  verified on a laptop only and is postponed).

## Unreleased (repository tidy-up)

- The 13 rc1 notebooks moved to `notebooks/legacy/` (they find the repository root from `pyproject.toml` now);
  `notebooks/` holds only `authoring/`, `templates/` and `legacy/`. The executor's `--legacy` flag, the hygiene
  tests, the notebook stripper's default paths and the release-package test follow.
- rc1 documents moved to `docs/legacy/` (group rotation runbook, participant and trainer guides, application
  inventory, resource sizing) with a README. Removed pages that were superseded or described the placeholder dataset:
  `data-dictionary`, `environment-validation`, `shared-services-runbook`, `dry-run-h200`, `dry-run-l40s`.
  `acceptance-checklist.md` is rewritten for `single_project`; the GPU runtime check moved into `runtime-profiles.md`.

## Unreleased (phoenix ui)

- Phoenix UI returned `Internal Server Error` while `/healthz` was OK: arize-phoenix 12.x calls the old
  `TemplateResponse(name, context)` signature, which Starlette 1.0 removed. `observability.in` now keeps
  `starlette>=0.46,<1`; `observability.lock` and `dev-test.lock` pin Starlette 0.52.1. The profile validator and a
  new test now check the UI page, not only `/healthz`.

## Unreleased (vllm host)

- vLLM launcher binds `127.0.0.1` by default. The `0.0.0.0` default failed in a CAI Application with
  `Address already in use` on the Application port. `VLLM_HOST` still overrides it.

## Unreleased (litellm master key)

- LiteLLM launcher: fails early with instructions when `LITELLM_MASTER_KEY` is not set (LiteLLM refuses to start
  without it). The deployment guide documents the key, its handling and the open question of client keys.

## Unreleased (litellm launcher)

- LiteLLM launcher: a relative `LITELLM_CONFIG` is resolved from the repository (the Application starts in
  `/home/cdsw`), the process runs from the repository root, a missing config gives a clear error, and variables the
  config reads as `os.environ/NAME` that are not set are reported.

## Unreleased (portal launcher in a kernel)

- CAI runs an Application script cell by cell in a kernel where `__file__` is undefined, so the Portal launcher
  failed with `NameError: name '__file__' is not defined`. The repository root now comes from
  `deployments.cai.common.REPO_ROOT`; a test runs every launcher without `__file__`.

## Unreleased (portal launcher)

- Workshop Portal and legacy Streamlit launchers: a CAI Application starts in `/home/cdsw`, not in the repository, so
  the relative `apps/workshop-portal/app.py` failed with "File does not exist". The script path is now resolved from
  the repository, the process runs from the repository root, and a missing script gives a clear error. Checked by
  starting Streamlit through the launcher from a different working directory.

## Unreleased (phoenix launcher)

- Phoenix Application launcher: `phoenix serve` has no `--host` or `--port` option (the Application failed with
  "unrecognized arguments"). The launcher now sets `PHOENIX_HOST` (default 127.0.0.1), `PHOENIX_PORT` (the platform
  port) and `PHOENIX_WORKING_DIR` in the child environment. Checked by starting the real server through the launcher
  and calling `/healthz`.

## Unreleased (qdrant binary preparation)

- Qdrant binary: `requirements/qdrant-binary-manifest.json` pins v1.19.2 (linux musl) with its SHA-256;
  `scripts/prepare_qdrant_binary.sh` (now a thin wrapper over `bni_training.qdrant_binary`) downloads over HTTPS,
  verifies the checksum, extracts the single `qdrant` executable and is safe to run again. The Application launcher
  checks the binary exists and says how to prepare it; it never downloads.

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

