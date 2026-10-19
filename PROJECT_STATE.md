# Project State

Last updated: 2026-10-19

## Status

Local development status: `local_validation_passed` (Python 3.10, macOS arm64, no NVIDIA GPU).

**CAI readiness is NOT claimed.** GPU, CUDA, vLLM, NFS model, live Impala and live CAI API validation are pending. A green local run proves the code, locks and mocks are sound; it does not prove the CAI environment.

## Verified Local Baseline

Commit `6529e38` on `feature/single-project-csv-workshop` (local only). Evidence that passed on the committed tree and
again from a fresh clean clone: 697 tests passed, Ruff clean, secret scan clean, all 13 notebooks executed locally,
dataset validator 21 of 21, tracked-file path audit and clean-clone validation PASS, `single_project` is the default
topology and explicit `multi_project` still returns the rc1 plan. Nothing is pushed. CAI readiness is NOT claimed.

## Next Milestone: Educational Notebook Redesign

Plan and handoff: `docs/plans/2026-10-19-educational-notebook-redesign.md` (plan only; nothing implemented yet).

- The current notebooks are executable but too wrapper-oriented: each one imports a lab script and calls `main()`.
- The notebook order and the 13 lab ids are retained.
- The trainer owns notebooks 01 and 02; participant hands-on begins with notebook 03.
- Participant notebooks will expose the meaningful code cell by cell (requests, SQL, semantic plans, agents, tools,
  Qdrant filters, spans, routes, guardrails). The Python files stay as reusable implementation and reference solutions.
- Shared vLLM remains one GPU Application, already running before hands-on; participant notebooks run on CPU Sessions.
- Streamlit remains one shared final Workshop Portal (single process, single replica).
- Two execution modes will be supported: `individual_learning` (preferred, about 40 CPU Sessions, one notebook copy
  and output folder per participant) and `group_driver` (fallback, 10 Sessions, one rotating driver per group).
- A folder is not a CAI Session. Real Session capacity (40 concurrent CPU Sessions), concurrent writes on the project
  filesystem and the participant dependency profile for notebooks 07 and 09 remain `cai-validation-pending`.

## Single-project CSV workshop branch (local only, not pushed)

Branch `feature/single-project-csv-workshop`, cut from the unmodified tag `v0.2.0-rc1`. `main`, the tag and the legacy
multi-project topology are untouched. Nothing from this branch has been pushed, deployed, or run on Cloudera AI.

Local validation passed (Python 3.10, macOS arm64): 697 tests pass, Ruff clean, secret scan clean, local
acceptance `local_validation_passed`, all 13 notebook templates execute in local mode, notebook hygiene clean,
dataset validator 21 of 21 checks, tracked-file path audit PASS, clean-clone validation `CLEAN_CLONE: PASS`.
This is **not** CAI readiness.

What exists locally:

- **Shared Workshop Portal** (one Streamlit Application for all ten groups): validated group selection, group locked
  after the first action with an explicit session reset, per-session isolation of chat, selections, outputs, temporary
  files, Qdrant results and telemetry, a shared inference gate (default 3 concurrent requests, queue, timeout, retry,
  cancel, overload handling), exactly one process and one replica (heartbeat guard; the CAI replica setting is still to
  be verified), LiteLLM-or-vLLM routing. Thread-based tests are not proof of real CAI browser capacity.
- **Synthetic banking dataset** (`data/raw`): 100 branches, 10,000 customers, 19,259 accounts, 101,903 transactions
  over 24 months, 5,000 loans; 12,088,835 bytes (limit 50 MB). Deterministic (seed 20260630, reference date
  2026-06-30), standard library only, identical bytes on Linux and macOS, no personal data, no BNI data, no credit
  decisioning. SHA-256: accounts `6ce3f1e3...`, branches `b2aab2d4...`, customers `07339c17...`, loans `31c2eb16...`,
  transactions `3ec309c1...` (full values in `data/manifests/checksums.json`).
- **Semantic layer** (`semantic/`): data dictionary, relationships, 18 executable metrics, business terms.
- **Ten logical group bundles** (`data/scenarios`) over the one physical dataset; every sample question of every
  mission returns rows; Group 06 can discover the 33 unusual patterns with ordinary queries. No anomaly flag, answer list or manifest is
  tracked or written to disk; the generator keeps the answer key in memory for the validator and tests only.
- **Guarded read-only CSV engine** (SQLite, sqlglot, authorizer, row cap, timeout). CSV is the default backend;
  Impala is optional, only with `DATA_BACKEND=impala`, never required and never a silent fallback.
- **Single-project dry-run plan** (the default of `plan`): 1 project, 10 group workspaces, up to 10 Sessions, 5 shared
  Applications, no per-group Streamlit Applications, active Application counts per phase never above 5.
  `WORKSHOP_TOPOLOGY=multi_project` (or `--topology multi_project`) returns the unchanged rc1 plan (11 projects,
  4 waves); an unknown value fails; the rc1 apply/wave commands require `multi_project`.
- **Ten-group workspace lifecycle**: seven scripts (`prepare_group_workspaces`, `validate_group_workspaces`,
  `assign_participants`, `reset_group_workspace`, `check_group_isolation`, `check_shared_services`,
  `archive_group_outputs`), dry run by default, idempotent, edited notebooks preserved, one group per reset, no
  secrets in `group.env`, 40 participants assigned with at most five per group. The `workshop/runtime/` hierarchy is
  generated and git-ignored.
- **Labs and notebooks 00-12 on the synthetic dataset**: registry `config/workshop/labs.yaml`, 13 notebook templates
  in `notebooks/templates/`, `--mode local|cai` (cai never mocks), labs 01-02 trainer-only (participants never
  start vLLM or download the model), rc1 script paths kept as thin wrappers, rc1 notebooks unchanged.
- **No anomaly answers anywhere in Git**: no flag column, manifest or incident IDs; the validator regenerates the
  patterns in memory.
- **Clean-clone validation**: `scripts/audit_local_paths.py` (fails on real local paths, does not match its own
  source) and `scripts/validate_clean_clone.py` (overall PASS or FAIL from a clone of HEAD).

Pending on CAI (registered in `config/cai-validation-pending.yaml`, all `cai-validation-pending`): GPU dependency
matrix; CPU-only PyTorch strategy for Linux RAG sessions; live Qdrant server; vLLM and Qwen model loading; CAI API v2
fields and the runtime identifier; live Impala authentication; real Portal capacity and sizing for about 40 browsers;
the single-replica setting and heartbeat behavior on CAI; running the dataset inside the CAI Application; group workspaces and the 13 notebooks inside ten CAI Sessions (`--mode cai`); live shared-service checks; the trainer's real roster. No CAI
readiness is claimed.

## Local Validation Passed

Baseline run before the hardening work (unmodified repository):

- 29 unit tests passed.
- `scripts/smoke_test.sh` and `scripts/acceptance_test.py --mode local` passed on Python 3.10.
- Secret scan clean.

That baseline also exposed defects that the 29 tests did not cover, now fixed (see below). The hardened results are recorded in the section "Hardened local validation".

## Completed local work

- Core synthetic Credit Portfolio Insight package and deterministic full-size dataset.
- Explicit CSV, Impala GSSAPI, and Impala LDAP data modes. No silent fallback after an authentication failure.
- Semantic model, SQL guardrails, Qdrant group isolation, and two-step workflow service.
- Python-native CAI Application entrypoints for shared vLLM, Qdrant, Phoenix, LiteLLM, and Streamlit.
- Streamlit group Application rotation in four waves (groups 01-03, 04-06, 07-09, 10) that enforces five active Applications in total.
- CAI API v2 lifecycle commands for one shared project and ten group projects (dry-run first).
- English scripts and notebooks 00 through 12 (registry-driven and migrated to the synthetic dataset).
- Local tests, acceptance runner, secret scan, and reproducible ZIP packaging.

## Local hardening completed

- Qdrant group filter uses native `qdrant-client` `Filter`/`FieldCondition`; REST JSON verified; local mode verified; retrieval asserts group isolation.
- All Ruff findings fixed without behavior changes.
- Dependency profiles redesigned: standalone fully resolved locks (`participant`, `rag`, `observability`, `gateway`, `guardrails`, `dev-test`), shared constraints only for `crewai`, `openai`, `pydantic`, `PyYAML`, `httpx` and an `onnxruntime` cap. Each is validated in its own temporary Python 3.10 venv by `scripts/validate_profiles.py`.
- The Phoenix server profile (`observability`) is isolated: no CrewAI, OpenAI or participant libraries and no shared constraints. Trace-sending clients (OpenTelemetry exporter, OpenInference instrumentors) are in `participant`.
- GPU profiles `gpu-l40s` and `gpu-h200` hold the intended vLLM 0.29.0 / torch 2.13.0 / transformers >=5.10.4 / cu13 metadata and are `cai-validation-pending`. They are not validated on macOS.
- Labs 00-12 support `--mode local` and `--mode cai`. Lab 07 indexes and retrieves through Qdrant, lab 08 runs a real CrewAI crew (explicit mock LLM in local mode), lab 09 verifies OpenInference traces in a real Phoenix server.
- Runtime profiles `local-macos`, `sandbox-l40s`, `bni-h200` with environment variable names only.
- Defects found and fixed (also: wrapt 2.x broke the OpenInference CrewAI instrumentor in the participant profile, now pinned `<2`): broken lab 02 import (`apps.vllm.start` did not exist); `CsvBackend` SQLite thread error under CrewAI tool calls; CrewAI `kickoff()` refused inside a Jupyter event loop; `observability` and `gateway` locks were incomplete and mutually inconsistent (Phoenix 20 vs 12, `litellm` without the proxy extra, `arize-phoenix-evals` 3.x and `graphql-core` 3.3 breaking `import phoenix`).

## Hardened local validation

Python 3.10.22, macOS arm64, no NVIDIA GPU. GPU, CUDA, vLLM, NFS and CAI checks are SKIPPED, not failed.

| Check | Result |
|---|---|
| Unit and integration tests | PASS, 142 passed (baseline was 29) |
| Ruff | PASS |
| Local smoke, local acceptance (`local_validation_passed`), secret scan | PASS |
| Each non-GPU profile in its own venv: install lock only, `pip check`, imports, labs | PASS: participant, rag, observability (real Phoenix server `/healthz`; CrewAI, OpenAI and LiteLLM proven absent), gateway (real LiteLLM proxy liveliness), guardrails, dev-test |
| `gpu-l40s`, `gpu-h200` | SKIPPED on macOS, `cai-validation-pending` |
| Labs 00-12 in `--mode local` | PASS, GPU/CAI/Impala/NFS steps SKIPPED with reasons |
| Notebooks 00-12 executed through nbclient in local mode | PASS, 13 of 13 |
| Lab 09: in-process spans in the participant profile; against a real temporary Phoenix server in dev-test | PASS, spans stored, OpenInference kinds AGENT/CHAIN/LLM, group_id present, no secret in traces |
| Qdrant group filter: local mode, REST JSON body, strict isolation | PASS |
| CAI API v2 dry-run plan | PASS: 11 projects, 4 Application waves, no API call |
| Clean temporary Git clone: acceptance, ruff, pytest, smoke, plan, notebooks | PASS |
| Notebooks: outputs, execution counts, timestamps, local paths, endpoints and tokens (`scripts/strip_notebooks.py --check`) | PASS, 13 of 13 clean |
| Tracked-file audit (no real local paths, secrets, caches, generated artifacts) | PASS (`scripts/audit_local_paths.py`, `scripts/validate_clean_clone.py`) |

Not run and not claimed: a live Qdrant server (only local mode and a captured REST request), real vLLM, real Impala, any CAI call.

## Educational notebook redesign milestones

- Labs 06-08 now use direct educational authoring sources and generated stripped templates. Lab 08
  executes the request-bound, group-scoped data tool before CrewAI orchestration, displays the user
  question, generated SQL, bounded result rows, Analyst output, and Reviewer output, and passes the
  same evidence sequentially to both agents. It does not claim that a mutable CrewAI recorder
  captured the call.
- Local execution of notebooks 06, 07, and 08 passed through `scripts/execute_notebooks.py` on
  2026-10-19. The Lab 08 execution test also verified the explicit tool-execution marker and the
  evidence hand-off to both agent requests.
- Regression at this milestone: 713 tests passed; Ruff passed for `src`, `tests`, `scripts`, and
  `apps`; generated notebook templates match their authoring sources. This is local validation only
  and does not change any CAI-pending status.
- Labs 09-11 now expose direct Phoenix tracing, bounded LiteLLM alias/fallback calls, and input,
  SQL, and output guardrails. Their generated notebooks passed local execution on 2026-10-19.
  Lab 09 uses an in-memory exporter locally and the environment-configured shared collector in CAI;
  participant notebooks never install or start Phoenix.
- Regression after the Labs 09-11 milestone: 716 tests passed; scoped Ruff and authoring/template
  synchronization passed. The two initial hygiene failures (credential-header examples matching the
  token scanner) were corrected before this passing run.
- Lab 12 now teaches the one-replica Portal flow directly: health, bounded queue states, session
  group lock, session-scoped output identity, and comparison with the Lab 05 group-bound SQL path.
  Its local in-process Portal execution passed, the migration allow-list was removed, and regression
  remained at 716 passing tests with scoped Ruff and authoring/template synchronization passing.
- Participant workspace modes are implemented and locally verified. `group_driver` is the default and
  creates ten group workspaces with driver-rotation notes. Explicit `individual_learning` consumes the
  ignored trainer assignment and creates 40 distinct anonymous `participant_01` through
  `participant_04` workspaces; notebooks write only to the active participant output. Targeted reset
  and archive work per participant. The dry-run plan reports 10 requested Sessions by default or 40
  capacity-pending Sessions when individual mode is explicit.
- Service configuration now uses the six documented URL variables: `VLLM_BASE_URL`, `QDRANT_URL`,
  `PHOENIX_COLLECTOR_ENDPOINT`, `PHOENIX_UI_URL`, `LITELLM_BASE_URL`, and
  `WORKSHOP_PORTAL_URL`. Regression after this milestone: 724 tests passed; scoped Ruff and generated
  notebook synchronization passed. This does not validate 40 real CAI Sessions or change CAI readiness.

## Environment-dependent validation (pending, not claimed)

Registered in `config/cai-validation-pending.yaml`; every item is `cai-validation-pending`: GPU dependency matrix, CPU-only torch strategy for Linux RAG sessions, live Qdrant server, vLLM and Qwen model loading, CAI API v2 fields, live Impala authentication.

- Run the PBJ Python 3.10 GPU probe (Lab 00) in the sandbox L40S runtime and at BNI on H200, then freeze the working torch, CUDA runtime, Transformers, and vLLM matrix into `gpu-l40s.lock` and `gpu-h200.lock`.
- Load Qwen3.5-9B BF16 from NFS on one L40S (sandbox) and one H200 (BNI) with TP=1.
- Validate the customer Impala GSSAPI or LDAP mode.
- Validate the shared Qdrant server (group isolation against the real server) and Phoenix NFS persistence.
- Validate ten simulated groups and three concurrent Streamlit Applications while vLLM and Qdrant are active.
- Compare CAI API v2 Application request fields with the target Swagger, obtain the PBJ runtime identifier from the target catalog, and run an operator-approved live dry run.
- Build and test the offline wheelhouse in the target-compatible PBJ runtime; decide the CPU-only torch wheel for the `rag` profile.
- Publish only one final Agent Studio workflow and account for its Model and Application resources.

## Packaging status

Local status: `local_validation_passed`. Customer-ready or CAI-ready status must not be claimed until every environment-dependent item above is complete. Update this file whenever one item changes state.
