# Notebook drafts

Redesign drafts that are **not** part of the 13 canonical templates. Nothing here is built into `notebooks/templates/`, copied into
group workspaces, or read by the tests. A draft is promoted by moving its source into `notebooks/authoring/` (under the canonical
name) and running `python scripts/build_notebooks.py`.

Labs 03 to 12 were redesigned as guided lessons and are canonical now (authoring and templates); their draft files were removed so there
is one source of truth. Use this folder for the next notebook to be redesigned (Labs 00, 01 and 02 still have the original wording).
Never run a notebook from here: open the copy in a group workspace, so `config/group.env` is found and the mode is `cai`.
