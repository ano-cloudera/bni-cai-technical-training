# workshop/

- `templates/` is source-controlled: the participant README and `group.env` templates and a roster example.
- `runtime/` is **generated** by `scripts/prepare_group_workspaces.py` and excluded from Git. It holds one folder per
  group plus a trainer-only `shared/` area. Never commit anything from it (no `group.env`, no rosters, no outputs).

The CSV dataset is never copied into group folders; every group reads `data/raw`.
