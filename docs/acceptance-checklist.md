# Acceptance Checklist

## Locally verified

- [ ] Full test suite passes.
- [ ] All 13 script/notebook pairs exist and contain no outputs or secrets.
- [ ] Synthetic data manifest matches generated files.
- [ ] Dry-run automation contains 11 projects and two Application waves.
- [ ] Development archive passes checksum and exclusion checks.

## Target CAI validation

- [ ] Python 3.10 PBJ Runtime compatibility report is captured.
- [ ] One H200 loads Qwen3.5-9B BF16 from NFS with TP=1.
- [ ] Impala GSSAPI or LDAP succeeds; CSV remains an explicit fallback.
- [ ] Qdrant and Phoenix persistence paths survive Application restart.
- [ ] Ten simulated groups can call vLLM and group filters remain isolated.
- [ ] The active Application count never exceeds five.
- [ ] With vLLM and Qdrant active, no more than three group Streamlit Applications run concurrently.
- [ ] API v2 live dry-run matches target Swagger and resource profiles.
- [ ] Offline wheelhouse installs in the target runtime.
- [ ] Room, power, projector, and Wi-Fi are ready for 40 participants.

