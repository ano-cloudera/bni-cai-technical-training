# Notebook drafts

Redesign drafts that are **not** part of the 13 canonical templates. Nothing here is built into `notebooks/templates/`,
copied into group workspaces, or read by the tests. A draft is promoted by moving its source into `notebooks/authoring/`
(under the canonical name) and running `python scripts/build_notebooks.py`.

## 04_csv_data_access_v2

Same lab as `notebooks/authoring/04_csv_data_access.py`, restructured as: one setup cell, ten explained steps (what the cell
does, why, what to look for, a prediction), one exercise, a closing list of what the participant proved, and the questions
to explain back. It keeps the saved file `04_dataset_preview.json` and the final `LAB_STATUS` line.

Try it in a group workspace (it does not touch the real Lab 04 notebook):

```bash
cp /home/cdsw/bni-cai-technical-training/notebooks/drafts/04_csv_data_access_v2.ipynb \
   /home/cdsw/workshop-runtime/groups/group_03/notebooks/
```

Open the copy from the group workspace, choose the kernel "BNI rag (py3.10)", and run all cells. Status: **not yet run**;
it was only syntax-checked.

## 05_semantic_layer_v2 and 06_crewai_tools_v2

Same pattern as Lab 04 v2 (setup cell, explained steps with a prediction, pandas tables, an exercise, a closing list of what was
proved). Lab 06's exercise now runs a second agent with the participant's goal and shows both answers side by side. Both were
executed locally (mock model) for group_03, group_05 and group_09 and passed; neither has run against the real services yet.
Try one in a group workspace the same way as Lab 04 v2 (copy the `.ipynb` there and open the copy).

## 07_qdrant_rag_v2 and 08_agent_workflow_v2

Same pattern again. Lab 07 teaches what an embedding is, similarity, the stored texts per group, the group filter, search, the
isolation check, a grounded prompt, and limit; Lab 08 teaches evidence-first, two agents with the same evidence, which numbers appear in the
answer, the grounding rule, a rejected invented number, and a reviewer whose criterion the participant changes. Both were executed locally
for group_03, group_05 and group_09 and passed. Neither has run against the real services (Qdrant with bge-m3, the shared vLLM) yet.
