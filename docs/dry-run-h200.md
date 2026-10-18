# H200 BNI Dry Run

1. Select the BNI PBJ Python 3.10 JupyterLab NVIDIA GPU runtime.
2. Confirm the observed H200, driver, and CUDA values with lab 00.
3. Copy `config/profiles/bni-h200.env.example` to an untracked `.env`. Install `gpu-h200` using `python scripts/bootstrap.py gpu-h200` (CAI validation pending).
4. Set `MODEL_PATH`, `GPU_PROFILE=h200`, and `APP_STARTUP_TIMEOUT_MINUTES=15`.
5. Deploy `deployments/cai/vllm/app.py` as the CAI Application script.
6. Verify `/health`, `/v1/models`, streaming and non-streaming chat, context length, and concurrent requests.
7. Run a ten-group client simulation and confirm latency, errors, tokens, and GPU memory.
8. Save the accepted runtime identifier and dependency versions for the workshop.
