# Trainer: workshop runbook (local preparation and CAI day)

Status: everything below passes locally. Nothing has run on Cloudera AI; each CAI step is `cai-validation-pending`
(`config/cai-validation-pending.yaml`). No CAI readiness is claimed. Run commands from the repository root with
`PYTHONPATH=src:.`. Commands that change files are dry runs until you pass `--apply` (or `--yes` for a reset).

## Before the workshop

1. **Clone and install** as in `docs/cai-workbench-clean-clone.md` (one dependency profile per environment).
2. **Check the dataset**: `python scripts/validate_dataset.py` (21 checks, ends in `RESULT: PASS`).
3. **Dry-run the plan** (no API call, single project by default):
   `python -m automation.cai_api_v2.cli --config config/env.sandbox-l40s.example.yaml plan --output build/cai-plan.json`
4. **Prepare the ten group workspaces**:
   ```bash
   python scripts/prepare_group_workspaces.py            # dry run: lists what would be created
   python scripts/prepare_group_workspaces.py --apply    # creates workshop/runtime/{shared,groups/group_01..10}
   python scripts/validate_group_workspaces.py           # structure, group.env, notebooks, no secrets
   ```
   Running it again is safe: unchanged files are left alone and participant-edited notebooks are never overwritten
   (`--overwrite --yes` replaces them after a backup under `shared/state/backups/`).
5. **Assign about 40 participants** (a CSV roster or `--count 40`; at most five per group by default):
   ```bash
   python scripts/assign_participants.py --roster roster.csv            # dry run, shows the summary
   python scripts/assign_participants.py --roster roster.csv --apply    # writes runtime/shared/state/
   ```
   The roster and assignment are trainer-only, stay outside Git, and use participant references, not personal data.
6. **Check the group boundaries**: `python scripts/check_group_isolation.py` (local probes in a temporary folder).
7. **Provision the shared Applications** (vLLM, Qdrant, Phoenix, LiteLLM, the single Portal) in the CAI UI. Lab 01
   (model files) and lab 02 (vLLM) are yours: participants never download the model or start vLLM.

## On the day

1. **Check the shared services for the phase** (read-only; it never starts or stops anything):
   `python scripts/check_shared_services.py --mode cai --phase day1`
   (phases `day1`, `day2_morning`, `agent_studio_publication`). `SKIPPED` means not active in this phase.
2. Tell each group its number. Participants open their Session, run notebook 00, then 03-11, then the Portal (lab 12).
3. Keep at most five Applications active (`config/workshop/application-lifecycle.yaml`).
4. If a group made a mess: `python scripts/reset_group_workspace.py --group-id group_04` (dry run), then `--yes`.
   Add `--include-notebooks` to restore the notebooks (edited ones are backed up first). Other groups are never touched.

## After the workshop

1. Save the results: `python scripts/archive_group_outputs.py --all --apply` (zips under `shared/state/archives/`;
   logs only with `--include-logs`). Archives are trainer-only and stay out of Git and out of the release package.
2. Stop the Applications you started. Delete `workshop/runtime/` when the data is no longer needed.

## Rules to keep

- One shared Qwen3.5-9B vLLM endpoint; one Qdrant collection filtered by `group_id`; one Phoenix; one LiteLLM; one
  Portal process and replica; at most five Applications active.
- Group separation is operational, not a security boundary. All data is synthetic.
- Never commit anything from `workshop/runtime/`, and keep secrets in the project environment only.
