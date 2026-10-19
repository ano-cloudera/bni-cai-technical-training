# Trainer: Sessions

- One CPU-only Jupyter Session per group (about 2 vCPU and 8 GB each as a starting point), up to ten at once.
  GPU is used only by the shared vLLM Application.
- `MAX_CONCURRENT_GROUP_SESSIONS` (default 10) controls how many Sessions the plan assumes. If the quota is lower,
  run wave A (group_01-05) then wave B (group_06-10). Waves change scheduling only, never folders, bundles or
  missions.
- Sessions are created in CAI by the trainer or participants. Whether the CAI API v2 can create them is unverified, so
  the dry-run plan only reports the requested count.
- Four people in one JupyterLab Session: one driver at a time, rotate roles, and save often. Real-time co-editing is
  not assumed.
- Real session capacity, quota and concurrent-write behavior are `cai-validation-pending`.
