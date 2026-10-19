# Dependency Profiles

Every CAI Application and lab environment uses **exactly one** standalone, fully resolved profile. Profiles are
never layered into one Python environment. A profile that needs participant libraries (`rag`, `observability`,
`dev-test`) includes them in its own `.in` file, so its lock is complete on its own.

| Profile | Used by | Includes | Local validation (macOS, Python 3.10) | CAI validation |
|---|---|---|---|---|
| `participant` | group Streamlit Application; labs 00-06 and 08-12 | | isolated venv, `pip check`, imports, labs (lab 09 verifies spans in-process) | pending |
| `rag` | lab 07, glossary indexing, `bni-qdrant` launcher | participant | isolated venv, `pip check`, imports, lab 07 | pending |
| `observability` | `bni-phoenix` Application (Phoenix **server** only) | nothing | isolated venv, `pip check`, imports, real Phoenix `/healthz`, proof that CrewAI/OpenAI are absent | pending |
| `gateway` | `bni-litellm` Application | | isolated venv, `pip check`, imports, real LiteLLM proxy liveliness | pending |
| `guardrails` | optional lab 11 extensions | | isolated venv, `pip check`, imports, lab 11 | pending |
| `dev-test` | local development and CI only | rag (with participant) and the Phoenix server | isolated venv, `pip check`, ruff, pytest, all 13 labs | not applicable |
| `gpu-l40s` | `bni-vllm-qwen35-9b` in the sandbox | | **not applicable on macOS** | **pending (Lab 00)** |
| `gpu-h200` | `bni-vllm-qwen35-9b` at BNI | | **not applicable on macOS** | **pending (Lab 00)** |

## Phoenix isolation

The `observability` profile installs only the Phoenix server. It does not install, include, or constrain CrewAI,
OpenAI, LiteLLM, or any participant library, and it is compiled without the shared constraints file. The libraries
that *send* traces (`opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, and the OpenInference CrewAI and
OpenAI instrumentors) live in `participant`. Lab 09 in a participant environment verifies spans in-process; with the
Phoenix server profile installed as well (`dev-test`, or a trainer machine) it also stores and re-reads them from a
real Phoenix server.

## Files

- `requirements/<profile>.in`: direct requirements and the reason for any cap.
- `requirements/<profile>.lock`: fully resolved pins, universal across Linux and macOS for Python 3.10.
- `requirements/constraints.txt`: the shared alignment file. It contains only `crewai`, `openai`, `pydantic`,
  `PyYAML`, `httpx` (versions the lab clients must share) and an `onnxruntime` cap that keeps every lock installable
  on Linux and on a Python 3.10 Mac. Nothing else belongs there.
- `requirements/profiles.yaml`: the registry, including validation status per profile.

## Recompile a profile

```bash
uv pip compile requirements/<profile>.in -c requirements/constraints.txt \
  --python-version 3.10 --universal --no-annotate -o requirements/<profile>.lock
```

## Validate every non-GPU profile in isolation

```bash
python scripts/validate_profiles.py            # all profiles; GPU profiles are reported SKIPPED
python scripts/validate_profiles.py --profile observability
```

Each profile gets a fresh temporary Python 3.10 virtual environment, installs **only its lock**, runs `pip check`,
imports its key libraries, and runs the labs or Application smoke checks it serves. `pip check` alone is not
enough: `arize-phoenix` passed `pip check` while failing to import (see below). The JSON report is written to
`build/profile-validation.json`.

## Constraints discovered by isolated validation

| Profile | Constraint | Why |
|---|---|---|
| `observability` | `arize-phoenix` 12.x (validated) | Moving to 20.x is no longer blocked by CrewAI because the server is isolated; it is a separate change that must be validated, including Python 3.10 support |
| `observability` | `arize-phoenix-evals<3` | Phoenix 12.35 imports `phoenix.evals.models`, removed in evals 3.x |
| `observability` | `graphql-core<3.3` | `strawberry-graphql` 0.287.x cannot import graphql-core 3.3 |
| `participant` | lab 09 avoids `phoenix.otel.register()` | `arize-phoenix-otel` 0.17.1 (newest for Python 3.10) reads `exporter._headers`, absent in OpenTelemetry >= 1.45; CrewAI 1.15 needs OpenTelemetry >= 1.42 |
| `gateway` | `litellm[proxy]` | The `litellm` CLI needs the proxy extra (uvicorn, FastAPI) |
| all | `onnxruntime<1.24` | No CPython 3.10 macOS arm64 wheel from 1.24 |

## GPU profiles (CAI validation pending)

The inputs now also declare PyYAML, packaging, requests, certifi, urllib3, cachetools and cloudpickle (missing in
the sandbox L40S validation); the locks are still stubs and regeneration is pending (`lock_status:
pending-regeneration` in `requirements/profiles.yaml`). `gpu-l40s` and `gpu-h200` hold the intended pin only. The intended matrix comes from the `vllm` 0.29.0 package
metadata on PyPI and is recorded in `requirements/profiles.yaml` and `requirements/compatibility-profiles.yaml`:

| Item | Intended value | Source |
|---|---|---|
| vLLM | 0.29.0 | `requirements/gpu-*.in` |
| PyTorch | 2.13.0 | vllm 0.29.0 metadata |
| Transformers | >= 5.10.4 | vllm 0.29.0 metadata |
| CUDA wheel family | cu13 | vllm 0.29.0 metadata |

These are intentions, not observations. They are **not validated on macOS and not validated in CAI**. Final pins are
confirmed by Lab 00 in the CAI sandbox (L40S) and again in the BNI runtime (H200); after that, freeze the observed
matrix into the lock file. Do not install vLLM or CUDA-specific PyTorch on macOS.

## CAI validation pending

`config/cai-validation-pending.yaml` registers what macOS cannot prove, each with the evidence required:
the GPU dependency matrix, the CPU-only PyTorch strategy for Linux RAG sessions, a live Qdrant server,
vLLM and Qwen model loading, the CAI API v2 fields, and live Impala authentication. All six are
`cai-validation-pending`.

## Open item: torch size in `rag` (cai-validation-pending)

`sentence-transformers` pulls PyTorch. On Linux the PyPI wheel brings the CUDA runtime wheels (several GB). Whether to
use a CPU-only torch wheel in the PBJ Standard runtime is decided in the CAI sandbox; embeddings run with
`device="cpu"`.
