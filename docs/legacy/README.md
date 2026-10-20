# Legacy documents (rc1 `multi_project` topology)

These pages describe the rc1 design: one shared project plus ten group projects, a Streamlit Application per group,
and rotation in four waves. That topology is still supported (`WORKSHOP_TOPOLOGY=multi_project`) but it is **not** the
default. For the default `single_project` workshop use:

- `docs/participant/` for participants and `docs/trainer/` for trainers,
- `docs/architecture/single-project-topology.md` for the design,
- `docs/trainer/cai-application-deployment.md` for creating the shared Applications.

| File | What it covers |
|---|---|
| `group-rotation-runbook.md` | Rotating the group Streamlit Applications in four waves |
| `participant-guide.md` | rc1 participant guide |
| `trainer-guide.md` | rc1 trainer guide and agenda |
| `application-inventory.md` | rc1 Application inventory per project |
| `resource-sizing.md` | rc1 resource sizing (eleven projects) |

The rc1 notebooks live in `notebooks/legacy/`. They are not used in the default flow; they run only through
`scripts/execute_notebooks.py --legacy` and the legacy tests.
