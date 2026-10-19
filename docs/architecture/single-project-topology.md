# Single-project topology (default)

`WORKSHOP_TOPOLOGY=single_project` is the default workshop topology on this branch. The rc1 `multi_project`
topology (one shared project plus ten group projects) is preserved and documented in
`docs/group-rotation-runbook.md`.

| Item | Single project |
|---|---|
| CAI Projects | 1 (`bni-ai-training-workshop`) |
| Participants / groups | 40 / 10, about 4 per group |
| Group workspace | A folder per group under `workshop/runtime/groups/<group_id>/` (generated, not in Git) |
| Sessions | Up to 10 CPU-only Jupyter Sessions, one per group (2 vCPU, 8 GB each as a starting point) |
| Shared Applications | vLLM, Qdrant, Phoenix, LiteLLM (Day 2), **one** Streamlit Workshop Portal. Maximum 5 active |
| Per-group Streamlit Applications | **None.** One Portal serves every group |
| Backend | CSV by default; Impala is an optional trainer demonstration |

## The Workshop Portal is a single process on purpose

The Portal limits simultaneous model requests with a semaphore (default 3, `PORTAL_MAX_CONCURRENT_INFERENCE`).
That limit lives inside one Python process. Therefore:

- The Application must run **one Streamlit process and one CAI Application replica** (`replicas: 1` in
  `config/workshop/applications.yaml`). Scaling out would multiply the limit and could overload the shared vLLM.
- The Portal refuses to start a second instance while the first one's heartbeat is fresh
  (`SingleInstanceGuard`, state in `workshop/runtime/shared/state/`). This is a best-effort guard; setting the
  replica count to one in CAI remains the authoritative control and must be verified in the sandbox.

## Group locking

A browser session chooses a group and is **locked** to it after its first chat or workflow action. Changing groups
requires an explicit **Reset session**, which cancels any running request and deletes that session's state,
outputs and temporary files. The reset never touches another session or group.

## Isolation is operational, not a security boundary

All participants are collaborators in one CAI project. Group folders, session ids and the Portal's validation
prevent accidents; they do not stop a determined collaborator who can open files in the project. All data is
fully synthetic.

## Datasets

The rc1 CSV dataset in `data/csv` is **only a temporary placeholder** for the Portal until the single-project
dataset slice (`data/raw`, ten group bundles) is completed. Sample questions and scenarios shown in the Portal
before that point are stand-ins.

## Pending on CAI

Real browser capacity and sizing, the single-replica setting, and Application accounting are all
`cai-validation-pending` (see `config/cai-validation-pending.yaml`). Nothing here claims CAI readiness.
