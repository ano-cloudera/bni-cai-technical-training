# Changelog

## Unreleased (feature/single-project-csv-workshop)

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

