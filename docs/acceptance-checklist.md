# Acceptance Checklist

## Locally verified

- [ ] Full test suite and Ruff pass on Python 3.10.
- [ ] Every non-GPU dependency profile installs and passes `pip check` in its own isolated venv (`scripts/validate_profiles.py`).
- [ ] All 13 labs run in `--mode local` with no FAIL; GPU, CAI, Impala and NFS steps are SKIPPED with a reason.
- [ ] Notebooks 00-12 execute in local mode through `scripts/execute_notebooks.py` without unfinished cells.
- [ ] A clean temporary Git clone repeats the local acceptance test.
- [ ] All 13 script/notebook pairs exist and contain no outputs or secrets.
- [ ] Synthetic data manifest matches generated files.
- [ ] Dry-run automation contains 11 projects and four Application waves (groups 01-03, 04-06, 07-09, and 10).
- [ ] Development archive passes checksum and exclusion checks.

## Target CAI validation

- [ ] Python 3.10 PBJ Runtime compatibility report is captured.
- [ ] Sandbox: one L40S loads Qwen3.5-9B BF16 from NFS with TP=1; Lab 00 values are frozen into `gpu-l40s.lock`.
- [ ] BNI: one H200 loads Qwen3.5-9B BF16 from NFS with TP=1; Lab 00 values are frozen into `gpu-h200.lock`.
- [ ] Impala GSSAPI or LDAP succeeds; CSV remains an explicit fallback.
- [ ] Qdrant and Phoenix persistence paths survive Application restart.
- [ ] Ten simulated groups can call vLLM and group filters remain isolated.
- [ ] The active Application count never exceeds five.
- [ ] With vLLM and Qdrant active, no more than three group Streamlit Applications run concurrently.
- [ ] API v2 live dry-run matches target Swagger and resource profiles.
- [ ] Offline wheelhouse installs in the target runtime.
- [ ] Room, power, projector, and Wi-Fi are ready for 40 participants.

