# Project State

Last updated: 2026-10-18

## Completed local work

- Core synthetic Credit Portfolio Insight package and deterministic full-size dataset.
- Explicit CSV, Impala GSSAPI, and Impala LDAP data modes.
- Semantic model, SQL guardrails, Qdrant group isolation, and two-step workflow service.
- Python-native CAI Application entrypoints for shared vLLM, Qdrant, Phoenix, LiteLLM, and Streamlit.
- Streamlit group Application rotation that enforces five active Applications in total.
- CAI API v2 lifecycle commands for one shared project and ten group projects.
- English scripts and notebooks 00 through 12.
- Local tests, acceptance runner, secret scan, and reproducible ZIP packaging.

## Environment-dependent validation

- Run the PBJ Python 3.10 GPU probe and pin the working torch, CUDA runtime, Transformers, and vLLM matrix.
- Load Qwen3.5-9B BF16 from NFS on one H200 with TP=1.
- Validate the customer Impala GSSAPI or LDAP mode.
- Validate Qdrant and Phoenix NFS persistence.
- Validate ten simulated groups and three concurrent Streamlit Applications while vLLM and Qdrant are active.
- Compare CAI API v2 Application request fields with the target Swagger and run an operator-approved live dry run.
- Build and test the offline wheelhouse in the target-compatible PBJ runtime.
- Publish only one final Agent Studio workflow and account for its Model and Application resources.

## Packaging status

Local development release status: `ready_for_cai_validation`. Customer-ready status must not be claimed until every environment-dependent item above is complete. Update this file whenever one item changes state.

