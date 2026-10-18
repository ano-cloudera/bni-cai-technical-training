# BNI Cloudera AI Technical Training Bundle

This repository is an English, ready-to-adapt workshop bundle for Cloudera AI 1.5.5 SP3, PBJ Runtime, Python 3.10, and JupyterLab. It teaches a fully synthetic Credit Portfolio Insight Assistant. It does not contain BNI data, credentials, model weights, or lending-decision logic.

## Start here

```bash
cp .env.example .env
set -a; source .env; set +a
python scripts/bootstrap.py participant
python scripts/00_environment_check.py
python scripts/05_impala_ask_data.py
```

The default path is CSV. Set `GROUP_ID` to the assigned value from `group_01` through `group_10`. Trainers provision the shared Applications before participant labs, but start only the services required by the current module. Do not exceed five active CAI Applications in total.

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
bash scripts/smoke_test.sh
python scripts/acceptance_test.py --mode local --report build/acceptance-local.md
```

GPU serving remains environment-dependent until the exact PBJ GPU Runtime matrix is validated. Run lab 00 first, pin the working CUDA, PyTorch, Transformers, and vLLM versions, then build the offline wheelhouse inside the same runtime family.

## CAI Application rule

Select the matching `deployments/cai/<service>/app.py` file in the CAI Application `Script` field. Use kernel `python3` and the approved PBJ Python 3.10 JupyterLab runtime. Do not use a shell script as the Application entrypoint.

The workshop limit is five active CAI Applications in total. During the Day 1 group UI rotation, keep vLLM and Qdrant active and run at most three group Streamlit Applications. Stop the group wave before starting Phoenix. LiteLLM is started for the Day 2 gateway lab.

# bni-cai-technical-training
