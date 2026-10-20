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
