# BNI Cloudera AI Technical Training Bundle

This repository is an English, ready-to-adapt workshop bundle for Cloudera AI 1.5.5 SP3, PBJ Runtime, Python 3.10, and JupyterLab. It teaches a fully synthetic Credit Portfolio Insight Assistant. It does not contain BNI data, credentials, model weights, or lending-decision logic.

## Start here

```bash
cp config/profiles/<runtime-profile>.env.example .env   # local-macos, sandbox-l40s, or bni-h200
set -a; source .env; set +a
python scripts/bootstrap.py participant                  # one standalone dependency profile per environment
python scripts/00_environment_validation.py --mode local # use --mode cai in a CAI Session
```

The exact CAI Workbench sequence is in `docs/cai-workbench-clean-clone.md`. Every lab supports `--mode local`
(mocks or local services, complete code path, GPU/CAI/Impala/NFS steps reported as `SKIPPED`) and `--mode cai`
(real services, no mocks, missing prerequisites are a `FAIL`). The default path is CSV. Trainers provision the shared
Applications before participant labs, but start only the services required by the current module. Do not exceed five
active CAI Applications in total.

### Participant flow

1. Open your group's CPU-only Session; your folder is `workshop/runtime/groups/<group_id>/`.
2. Run notebook `00_environment_validation`; it shows your `GROUP_ID`, `DATASET_ID`, `MISSION_ID` and workspace.
3. Run notebooks 03-11 in order against the one shared model endpoint. Notebooks 01 and 02 are trainer-only: you never
   download the model and never start vLLM.
4. Finish with notebook 12 and the shared Workshop Portal. Everything you save goes to your group's `output/` folder.

### Trainer flow

```bash
python scripts/validate_dataset.py
python scripts/prepare_group_workspaces.py --apply     # dry run without --apply
python scripts/validate_group_workspaces.py
python scripts/assign_participants.py --roster roster.csv --apply
python scripts/check_group_isolation.py
python scripts/check_shared_services.py --mode cai --phase day1
python scripts/reset_group_workspace.py --group-id group_04 --yes   # one group only, dry run without --yes
python scripts/archive_group_outputs.py --all --apply
```

Details: `docs/trainer/workshop-runbook.md` and `docs/architecture/workspace-lifecycle.md`.

## Labs and notebooks

`config/workshop/labs.yaml` is the registry of the 13 labs; notebook templates are in `notebooks/templates/`.

| ID | Lab | Audience |
|---|---|---|
| 00 | Environment Validation | trainer, participant |
| 01 | Model Artifact Validation | trainer only |
| 02 | vLLM Deployment | trainer demo |
| 03 | LLM API Testing | participant |
| 04 | CSV Data Access | participant |
| 05 | Semantic Layer | participant |
| 06 | CrewAI Tools | participant |
| 07 | Qdrant RAG | participant |
| 08 | Agent Workflow | participant |
| 09 | Phoenix Monitoring | participant |
| 10 | LiteLLM Routing | participant |
| 11 | Input and Output Guardrails | participant |
| 12 | End-to-End Workshop Portal | participant |

The rc1 script paths (for example `scripts/00_environment_check.py`) and the rc1 notebooks in `notebooks/` still work.

## Repository paths

- `notebooks/templates/`: the 13 notebook templates; `notebooks/`: the rc1 notebooks.
- `scripts/`: canonical labs `00_*` to `12_*`, the seven workspace scripts and operations.
- `src/bni_training/`: reusable application logic.
- `workshop/`: workspace templates (tracked) and the generated `runtime/` hierarchy (git-ignored).
- `deployments/cai/`: Python-native CAI Application entrypoints and API v2 manifests.
- `apps/`: service implementation code used by the launchers.
- `automation/cai_api_v2/`: dry-run-first CAI project and Application automation.
- `data/`: deterministic synthetic dataset (`raw`), manifests, scenarios and generator.
- `docs/participant/`, `docs/trainer/`, `docs/architecture/`: the guides.

## Local verification

```bash
python scripts/bootstrap.py dev-test                      # inside a Python 3.10 virtual environment
PYTHONPATH=src:. pytest -q
ruff check src automation scripts tests deployments apps data
bash scripts/smoke_test.sh
python scripts/acceptance_test.py --mode local --report build/acceptance-local.md
python scripts/validate_profiles.py                       # every non-GPU profile in its own temporary venv
python scripts/execute_notebooks.py                       # the 13 notebook templates in local mode
python scripts/audit_local_paths.py                       # tracked files must contain no real local path
python scripts/validate_clean_clone.py                    # clones HEAD; ends in CLEAN_CLONE: PASS or FAIL
```

Local validation is **not** CAI readiness. See `docs/runtime-profiles.md` for which checks are PASS, SKIPPED, or
mandatory in `local-macos`, `sandbox-l40s`, and `bni-h200`, and `docs/dependency-profiles.md` for the profile design.
GPU serving remains environment-dependent until the exact PBJ GPU Runtime matrix is validated. Run lab 00 first, pin the working CUDA, PyTorch, Transformers, and vLLM versions, then build the offline wheelhouse inside the same runtime family.

## CAI Application rule

Select the matching `deployments/cai/<service>/app.py` file in the CAI Application `Script` field. Use kernel `python3` and the approved PBJ Python 3.10 JupyterLab runtime. Do not use a shell script as the Application entrypoint.

The workshop limit is five active CAI Applications in total. During the Day 1 group UI rotation, keep vLLM and Qdrant active and run at most three group Streamlit Applications. Stop the group wave before starting Phoenix. LiteLLM is started for the Day 2 gateway lab.

## Workshop topology

The default topology is `single_project` (used when `WORKSHOP_TOPOLOGY` is unset): one CAI Project, ten group
workspaces, and **one shared Streamlit Workshop Portal** for all groups (exactly one Streamlit process and one
Application replica, because the inference concurrency limit is process-local). The rc1 `multi_project` topology is
preserved and must be selected explicitly (`WORKSHOP_TOPOLOGY=multi_project`); an unknown value is rejected. See
`docs/architecture/single-project-topology.md`.

### Synthetic dataset and ten group missions

`data/raw` holds one fully synthetic, deterministic banking dataset (branches, customers, accounts, transactions,
loans; 12 MB, no personal data, no BNI data). `data/scenarios` defines ten **logical bundles** of it, one mission
per group, without copying the data. CSV is the default backend (`DATA_BACKEND=csv`); Impala is an optional,
trainer-controlled extension and is never required. Group separation is operational, not a security boundary.

```bash
python scripts/validate_dataset.py                      # 21 checks, prints PASS or FAIL
python scripts/generate_synthetic_data.py --preview     # nothing is written
PORTAL_MODE=local streamlit run apps/workshop-portal/app.py   # laptop demo with a mock model
PYTHONPATH=src:. python -m automation.cai_api_v2.cli --config config/env.sandbox-l40s.example.yaml \
  plan --output build/cai-plan.json   # dry run, no API call; single_project is the default
```

Docs: `docs/participant/`, `docs/trainer/`, `docs/architecture/dataset-and-semantic-layer.md`.

The rc1 CSV dataset in `data/csv` is kept only for the legacy topology and the rc1 notebooks. Local validation is
not CAI readiness: GPU matrix, live Qdrant, vLLM and model loading, CAI API v2 fields, Portal capacity, group
workspaces inside CAI Sessions and live Impala all remain `cai-validation-pending`.
