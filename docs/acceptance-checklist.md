# Acceptance Checklist (default `single_project` topology)

Tick an item only with evidence. Local validation is not CAI readiness.

## Locally verified

- [ ] Full test suite and Ruff pass on Python 3.10; secret scan and `scripts/audit_local_paths.py` are clean.
- [ ] Every non-GPU dependency profile installs and passes `pip check` in its own isolated venv
      (`scripts/validate_profiles.py`); the Phoenix profile also returns its UI page, not only `/healthz`.
- [ ] The 13 canonical labs run in `--mode local` with no FAIL; GPU, CAI, Impala and NFS steps are SKIPPED with a reason.
- [ ] The 13 notebook templates execute in local mode (`scripts/execute_notebooks.py`) and are stripped
      (`scripts/strip_notebooks.py --check`); authoring sources and templates match (`scripts/build_notebooks.py --check`).
- [ ] The synthetic dataset validates (`scripts/validate_dataset.py`) and regenerates to identical checksums.
- [ ] Ten group workspaces are generated and validate; 40 participants are assigned (`scripts/assign_participants.py`).
- [ ] The default plan is `single_project` (1 project, 10 workspaces, 5 Applications, no per-group Streamlit);
      explicit `multi_project` still returns the rc1 plan.
- [ ] A clean clone passes `scripts/validate_clean_clone.py`; the release package excludes `workshop/runtime`.

## Target CAI validation (all pending until evidence is recorded)

- [ ] Python 3.10 PBJ Runtime report captured (lab 00).
- [ ] vLLM: Qwen3.5-9B BF16 loaded from NFS with TP=1 **as a CAI Application** (sandbox L40S/A10G, then BNI H200);
      `/health`, `/v1/models`, chat, streaming and concurrent requests pass.
- [ ] Qdrant binary prepared; Qdrant Application Running; a collection survives a restart.
- [ ] Phoenix Application Running with a working UI; a trace from lab 09 appears.
- [ ] LiteLLM Application Running with a master key; routing and fallback pass (lab 10).
- [ ] Workshop Portal Application Running as one process and one replica; a sample question completes (lab 12).
- [ ] Access between Applications and from other Sessions works, including CAI authentication.
- [ ] The active Application count never exceeds five.
- [ ] Group workspaces and the 13 notebooks work in real Sessions in `--mode cai` (`group_driver`); 40 concurrent
      Sessions (`individual_learning`) are validated only if the quota allows.
- [ ] Portal capacity for about 40 browsers, and the Session quota, are measured.
- [ ] Impala GSSAPI or LDAP succeeds if it is used; CSV remains the default.
- [ ] CAI API v2 live dry run matches the target Swagger and resource profiles.
- [ ] Room, power, projector and Wi-Fi are ready for 40 participants.

Record each result in `PROJECT_STATE.md` and `config/cai-validation-pending.yaml`.
