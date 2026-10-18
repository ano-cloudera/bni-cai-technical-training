# Codex Working Agreement

Use Python 3.10-compatible syntax and keep all code, notebooks, and documentation in English. Read `PROJECT_STATE.md` before changing behavior and update it after every validated milestone.

Preserve these invariants:

- Fully synthetic data only.
- Ten group IDs, `group_01` through `group_10`.
- One shared Qwen3.5-9B vLLM endpoint on one H200, BF16, TP=1.
- One shared Qdrant collection with a mandatory `group_id` filter.
- One shared Phoenix and one shared LiteLLM Application.
- No more than five group Streamlit Applications active concurrently.
- Impala GSSAPI, Impala LDAP, and CSV are explicit modes. Never silently fall back after authentication failure.
- Secrets come from environment variables and must never appear in commits, logs, traces, notebooks, or archives.
- Model weights remain on NFS and are never packaged.

Run `PYTHONPATH=src:. pytest -q`, `bash scripts/smoke_test.sh`, and local acceptance before packaging. Use the CAI API v2 CLI in dry-run mode until the target Swagger, runtime identifiers, and resource profiles are validated.

