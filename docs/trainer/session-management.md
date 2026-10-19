# Trainer: Sessions

- Default `group_driver`: one CPU-only Jupyter Session per group (about 2 vCPU and 8 GB each as a starting point),
  up to ten at once. Four anonymous drivers rotate using `driver-rotation.md`.
- Optional `individual_learning`: up to 40 CPU Sessions and 40 isolated participant folders. Do not enable it until
  CAI quota, startup time, and concurrent shared-service load are validated.
  GPU is used only by the shared vLLM Application.
- `MAX_CONCURRENT_GROUP_SESSIONS` (default 10) controls how many Sessions the plan assumes. If the quota is lower,
  run wave A (group_01-05) then wave B (group_06-10). Waves change scheduling only, never folders, bundles or
  missions.
- Sessions are created in CAI by the trainer or participants. Whether the CAI API v2 can create them is unverified, so
  the dry-run plan only reports the requested count.
- Generate assignments before individual folders: run `assign_participants.py --apply`, then
  `prepare_group_workspaces.py --mode individual_learning --apply`. The generated `participant_01` through
  `participant_04` labels do not depend on CAI identity.
- Real session capacity, quota and concurrent-write behavior are `cai-validation-pending`.
