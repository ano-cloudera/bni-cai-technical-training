# BNI Cloudera AI Technical Training Bundle

This repository is an English, ready-to-adapt workshop bundle for Cloudera AI 1.5.5 SP3, PBJ Runtime, Python 3.10, and JupyterLab. It teaches a fully synthetic Credit Portfolio Insight Assistant. It does not contain BNI data, credentials, model weights, or lending-decision logic.

## Start here

```bash
cp config/profiles/<runtime-profile>.env.example .env   # local-macos, sandbox-l40s, or bni-h200
set -a; source .env; set +a
python scripts/bootstrap.py participant                  # one standalone dependency profile per environment
python scripts/00_environment_check.py --mode cai        # use --mode local on a laptop without a GPU
python scripts/05_impala_ask_data.py --mode cai
```

The exact CAI Workbench sequence is in `docs/cai-workbench-clean-clone.md`. Every lab supports `--mode local`
(mocks or local services, complete code path, GPU/CAI/Impala/NFS steps reported as `SKIPPED`) and `--mode cai`
(real services, no mocks, missing prerequisites are a `FAIL`). The default path is CSV. Set `GROUP_ID` to the assigned value from `group_01` through `group_10`. Trainers provision the shared Applications before participant labs, but start only the services required by the current module. Do not exceed five active CAI Applications in total.

## Repository paths

- `notebooks/`: labs 00 through 12 for JupyterLab.
- `scripts/`: matching canonical Python labs and operations.
- `src/bni_training/`: reusable application logic.
- `deployments/cai/`: Python-native CAI Application entrypoints and API v2 manifests.
- `apps/`: service implementation code used by the launchers.
- `automation/cai_api_v2/`: dry-run-first CAI project and Application automation.
- `data/`: deterministic synthetic dataset, generator, glossary, and Impala SQL.
- `docs/participant-guide.md`: participant path.
- `docs/trainer-guide.md`: trainer preparation and schedule.

## Local verification

```bash
python scripts/bootstrap.py dev-test                      # inside a Python 3.10 virtual environment
PYTHONPATH=src:. pytest -q
ruff check src automation scripts tests deployments apps data
bash scripts/smoke_test.sh
python scripts/acceptance_test.py --mode local --report build/acceptance-local.md
python scripts/validate_profiles.py                       # every non-GPU profile in its own temporary venv
python scripts/execute_notebooks.py                       # notebooks 00-12 in local mode
```

Local validation is **not** CAI readiness. See `docs/runtime-profiles.md` for which checks are PASS, SKIPPED, or
mandatory in `local-macos`, `sandbox-l40s`, and `bni-h200`, and `docs/dependency-profiles.md` for the profile design.
GPU serving remains environment-dependent until the exact PBJ GPU Runtime matrix is validated. Run lab 00 first, pin the working CUDA, PyTorch, Transformers, and vLLM versions, then build the offline wheelhouse inside the same runtime family.

## CAI Application rule

Select the matching `deployments/cai/<service>/app.py` file in the CAI Application `Script` field. Use kernel `python3` and the approved PBJ Python 3.10 JupyterLab runtime. Do not use a shell script as the Application entrypoint.

The workshop limit is five active CAI Applications in total. During the Day 1 group UI rotation, keep vLLM and Qdrant active and run at most three group Streamlit Applications. Stop the group wave before starting Phoenix. LiteLLM is started for the Day 2 gateway lab.

## Workshop topology

The default topology is `single_project`: one CAI Project, ten group workspaces, and **one shared Streamlit
Workshop Portal** for all groups (exactly one Streamlit process and one Application replica, because the inference
concurrency limit is process-local). The rc1 `multi_project` topology is preserved. See
`docs/architecture/single-project-topology.md`.

### Synthetic dataset and ten group missions

`data/raw` holds one fully synthetic, deterministic banking dataset (branches, customers, accounts, transactions,
loans; 12 MB, no personal data, no BNI data). `data/scenarios` defines ten **logical bundles** of it, one mission
per group, without copying the data. CSV is the default backend (`DATA_BACKEND=csv`); Impala is an optional,
trainer-controlled extension and is never required. Group separation is operational, not a security boundary.

```bash
python scripts/validate_dataset.py                      # 22 checks, prints PASS or FAIL
python scripts/generate_synthetic_data.py --preview     # nothing is written
PORTAL_MODE=local streamlit run apps/workshop-portal/app.py   # laptop demo with a mock model
PYTHONPATH=src:. python -m automation.cai_api_v2.cli --config config/env.sandbox-l40s.example.yaml \
  plan --topology single_project --output build/cai-plan.json   # dry run, no API call
```

Docs: `docs/participant/`, `docs/trainer/`, `docs/architecture/dataset-and-semantic-layer.md`.

The CSV dataset in `data/csv` is **only a temporary placeholder** for the legacy topology and notebooks 00-12, which
are not yet migrated to `data/raw`. Local validation is not CAI readiness: GPU matrix, live Qdrant, vLLM and model
loading, CAI API v2 fields, Portal capacity and live Impala all remain `cai-validation-pending`.
