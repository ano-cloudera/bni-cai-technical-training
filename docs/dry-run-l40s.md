# L40S Sandbox Dry Run

1. Select the PBJ Python 3.10 JupyterLab NVIDIA GPU runtime.
2. Install `gpu-l40s` using `python scripts/bootstrap.py gpu-l40s`.
3. Set `MODEL_PATH`, `GPU_PROFILE=l40s`, and the CAI Application port variables.
4. Run labs 00, 01, 02, and 03.
5. Verify `/health`, `/v1/models`, one non-streaming request, one streaming request, and a small concurrency test.
6. Record runtime identifier, driver, CUDA runtime, torch, transformers, and vLLM versions.

Passing this checklist validates the sandbox only. It does not certify H200.
