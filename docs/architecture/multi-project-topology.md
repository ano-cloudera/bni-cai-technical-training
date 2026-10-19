# Multi-project topology (legacy, preserved)

`WORKSHOP_TOPOLOGY=multi_project` is the rc1 design: one shared project `bni-ai-training-shared` plus ten group
projects, with a Streamlit Application per group rotated in four waves while vLLM and Qdrant stay active (at most
five Applications active, three group Applications at a time). It is still fully supported:

- `plan` defaults to this topology unless `--topology single_project` or `WORKSHOP_TOPOLOGY=single_project` is set; the
  output is the rc1 plan (11 projects, 4 waves).
- The rc1 labs, the group Streamlit Application and the placeholder dataset in `data/csv` are unchanged.
- Runbook: `docs/group-rotation-runbook.md`.

The single-project topology (`docs/architecture/single-project-topology.md`) is the default workshop design on the
`feature/single-project-csv-workshop` branch.
