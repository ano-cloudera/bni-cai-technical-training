# PBJ GPU Runtime Validation

Run `python scripts/00_environment_check.py` inside the target Python 3.10 PBJ GPU session before installing vLLM. The report must show Python 3.10, NVIDIA H200 NVL, a visible CUDA runtime, and a compatible PyTorch build. Pin the tested `torch`, `transformers`, and `vllm` versions only after this check. A driver capability shown by `nvidia-smi` is not the same as the CUDA runtime bundled with PyTorch.

