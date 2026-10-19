# Group workspace lifecycle

`scripts/prepare_group_workspaces.py` generates a git-ignored hierarchy. It never copies the dataset.

```text
workshop/runtime/
  shared/{config,state,logs}            trainer-only (roster, assignment, backups, archives)
  groups/group_01 ... group_10/
    config/group.env                    non-secret: GROUP_ID, DATASET_ID, MISSION_ID, GROUP_WORKSPACE, ...
    config/workspace-manifest.json      template checksums used to detect participant edits
    notebooks/                          copies of notebooks/templates/*.ipynb (13)
    output/  logs/  tmp/                saved reports, logs, temporary files of that group only
    driver-rotation.md                  default group_driver turn-taking
    participants/participant_01...04/   optional individual_learning notebooks/output/logs/tmp
    README.md                           participant instructions
```

## Rules

- **Registry-driven.** `config/workshop/labs.yaml` lists the 13 labs and their notebook templates; the scripts, the
  builder, the executor and the workspace manager read it. Nothing depends on file name order.
- **Idempotent.** A second run changes nothing. A notebook the participants edited is kept; `--overwrite --yes`
  replaces it after a backup to `shared/state/backups/<group>/<timestamp>/`.
- **Dry run first.** Without `--apply` (or `--yes` for a reset) the scripts only report what they would do, using the
  same code path as the real run.
- **One group at a time.** Every path goes through `group_paths.safe_join`: group ids are validated, names cannot
  climb out of the group folder, and a reset touches one group only.
- **No secrets.** `group.env` holds names and ids only; the validator rejects secret-looking keys and values.
- **Lab context.** Every participant lab resolves `GROUP_ID`, `DATASET_ID`, `MISSION_ID` and `GROUP_WORKSPACE` from the
  environment first, then `group.env`. A conflict between the two is an error. In `--mode cai` nothing is guessed; in
  `--mode local` the labs use group_01 and a throwaway workspace.
- **Operational isolation only.** `check_group_isolation.py` proves the guards work; it is not a security boundary.
- **Two explicit modes.** `group_driver` is the default and creates no participant folders. `individual_learning`
  reads the ignored trainer assignment and creates anonymous participant workspaces; without an assignment it creates
  none and reports why.

## Labs and notebooks

| Lab | Notebook template | Audience |
|---|---|---|
| 00 Environment Validation | `00_environment_validation` | trainer, participant |
| 01 Model Artifact Validation | `01_model_artifact_validation` | trainer only; no download by default |
| 02 vLLM Deployment | `02_vllm_deployment` | trainer demo; starts vLLM only with `WORKSHOP_ROLE=trainer` and `TRAINER_EXECUTE_VLLM=true` |
| 03 LLM API Testing | `03_llm_api_testing` | participant |
| 04 CSV Data Access | `04_csv_data_access` | participant |
| 05 Semantic Layer | `05_semantic_layer` | participant |
| 06 CrewAI Tools | `06_crewai_tools` | participant |
| 07 Qdrant RAG | `07_qdrant_rag` | participant |
| 08 Multi-Agent Workflow | `08_agent_workflow` | participant |
| 09 Phoenix Monitoring | `09_phoenix_monitoring` | participant |
| 10 LiteLLM Routing | `10_litellm_routing` | participant |
| 11 Input and Output Guardrails | `11_guardrails` | participant |
| 12 End-to-End Workshop Portal | `12_end_to_end_portal` | participant |

Labs 03-12 use the one shared vLLM endpoint. Each lab takes `--mode local|cai`: local runs the full code path with
explicit mocks or local services and reports GPU, NFS, CAI and Impala steps as `SKIPPED`; cai never mocks. The old
rc1 script paths remain as thin wrappers (`scripts/00_environment_check.py`, ...) and the rc1 notebooks still run.
