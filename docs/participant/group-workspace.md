# Your group workspace

- **Saved answers:** every completed answer is stored as JSON under
  `workshop/runtime/groups/<your group>/output/<your session id>/`. You can download them from *My outputs*.
- **Temporary files:** `tmp/<your session id>/` next to it. Both folders belong to your browser session only.
- **Shared data:** all groups read the same CSV files in `data/raw/` (never copied per group) through the Portal,
  which shows only the tables of your mission.
- **Never touch:** `data/`, `semantic/`, `src/`, `config/`, `deployments/` and other groups' folders.

`workshop/runtime/` is created when the Portal runs and is excluded from Git. A trainer can see every group's folder.
Reset session (see *Getting started*) deletes your own session folders only.
