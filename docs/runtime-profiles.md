# Runtime Profiles and Check Policy

Three explicit runtime profiles exist. Each has `config/profiles/<name>.yaml` (required environment variable
**names** and check policy) and `config/profiles/<name>.env.example` (documented example values). Nothing in the
repository contains a runtime identifier, model path, credential, host, or port; values come from environment
variables. Copy the example to an untracked `.env`.

| Profile | Where | GPU | Default lab mode | Data mode |
|---|---|---|---|---|
| `local-macos` | developer Mac | none | `local` | `csv` |
| `sandbox-l40s` | CAI sandbox, PBJ Python 3.10 | NVIDIA L40S (`GPU_PROFILE=l40s`, `gpu-l40s`) | `cai` | `csv` |
| `bni-h200` | BNI CAI, PBJ Python 3.10 | NVIDIA H200 NVL (`GPU_PROFILE=h200`, `gpu-h200`) | `cai` | explicit `impala_gssapi`, `impala_ldap`, or `csv` |

Select with `RUNTIME_PROFILE`. Lab 00 in `--mode cai` fails when it is unset or when a required variable is missing.

## Lab modes

- `--mode local` (or `LAB_MODE=local`): mocks or local services, complete code path, no cluster. Anything that needs a
  GPU, CAI, Impala, or the NFS model is reported **SKIPPED** with a reason, never FAILED.
- `--mode cai` (or `LAB_MODE=cai`): real services from environment variables. No mocks. A missing prerequisite is a
  **FAIL**, and an Impala failure never falls back to CSV.

Every lab prints its checks and one final `LAB_STATUS:` line. Exit code 0 = PASS, 3 = SKIPPED (nothing could run),
1 = FAIL.

## Check policy

MANDATORY means the check must PASS in that environment. SKIPPED means it does not apply there and is reported as
SKIPPED. OPTIONAL means run it when available. The last column is the result of the run recorded in
`PROJECT_STATE.md`.

| Check | local-macos | sandbox-l40s | bni-h200 | Recorded on macOS |
|---|---|---|---|---|
| Unit and integration tests | MANDATORY | MANDATORY | MANDATORY | PASS (121 passed) |
| Ruff lint | MANDATORY | MANDATORY | MANDATORY | PASS |
| Each non-GPU profile in an isolated venv (`validate_profiles.py`) | MANDATORY | MANDATORY | MANDATORY | PASS (6 of 6 non-GPU; 2 GPU SKIPPED) |
| Local smoke (`smoke_test.sh`) | MANDATORY | MANDATORY | MANDATORY | PASS |
| Local acceptance (`acceptance_test.py --mode local`) | MANDATORY | MANDATORY | MANDATORY | PASS (`local_validation_passed`) |
| Notebooks in local mode (`execute_notebooks.py`) | MANDATORY | MANDATORY | OPTIONAL | PASS (13 of 13, executed) |
| Clean clone repeats local acceptance | MANDATORY | MANDATORY | MANDATORY | PASS |
| Lab 00 GPU visible | SKIPPED | MANDATORY | MANDATORY | SKIPPED |
| CUDA runtime and torch build | SKIPPED | MANDATORY | MANDATORY | SKIPPED |
| vLLM serving Qwen3.5-9B BF16, TP=1 | SKIPPED | MANDATORY | MANDATORY | SKIPPED |
| Model load from NFS | SKIPPED | MANDATORY | MANDATORY | SKIPPED |
| Impala GSSAPI or LDAP | SKIPPED | OPTIONAL | MANDATORY | SKIPPED |
| Shared Qdrant server and group isolation | SKIPPED (local-mode Qdrant instead) | MANDATORY | MANDATORY | SKIPPED |
| Shared Phoenix traces | OPTIONAL (temporary local Phoenix) | MANDATORY | MANDATORY | PASS (lab 09, real local Phoenix) |
| LiteLLM proxy | OPTIONAL (profile smoke) | MANDATORY | MANDATORY | PASS (real proxy liveliness) |
| CAI API v2 dry-run plan (no API call) | MANDATORY | MANDATORY | MANDATORY | PASS (11 projects, 4 waves) |
| CAI API v2 live calls | SKIPPED | OPTIONAL (operator approval) | MANDATORY | SKIPPED |
| Streamlit group waves (4 waves, <= 5 active Applications) | SKIPPED | MANDATORY | MANDATORY | SKIPPED |
| Ten-group concurrency against vLLM | SKIPPED | MANDATORY | MANDATORY | SKIPPED |

A green `local-macos` column is evidence that the code and locks are sound. It is **not** evidence of CAI readiness.
