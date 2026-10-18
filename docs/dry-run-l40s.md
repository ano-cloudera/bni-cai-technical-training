# L40S Sandbox Dry Run

1. Select the PBJ Python 3.10 JupyterLab NVIDIA GPU runtime.
2. Copy `config/profiles/sandbox-l40s.env.example` to an untracked `.env` and fill the placeholders. Install `gpu-l40s` using `python scripts/bootstrap.py gpu-l40s` (CAI validation pending; intended matrix in `docs/dependency-profiles.md`).
3. Confirm `MODEL_PATH` and `GPU_PROFILE=l40s`. CAI injects the Application port variables.
4. Run labs 00, 01, 02, and 03 with `--mode cai`.
5. Verify `/health`, `/v1/models`, one non-streaming request, one streaming request, and a small concurrency test.
6. Record runtime identifier, driver, CUDA runtime, torch, transformers, and vLLM versions.

Passing this checklist validates the sandbox only. It does not certify H200.
