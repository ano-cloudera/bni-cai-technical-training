# Notebook drafts

Redesign drafts that are **not** part of the 13 canonical templates. Nothing here is built into `notebooks/templates/`, copied into
group workspaces, or read by the tests. A draft is promoted by moving its source into `notebooks/authoring/` (under the canonical
name) and running `python scripts/build_notebooks.py`.

Labs 04 to 08 were drafted here, tried in the sandbox, and promoted to `notebooks/authoring/` (they are the canonical guided
notebooks now; the draft files were removed so there is one source of truth). Use this folder for the next lab to be redesigned.
Never run a notebook from here: open the copy in a group workspace, so `config/group.env` is found and the mode is `cai`.
