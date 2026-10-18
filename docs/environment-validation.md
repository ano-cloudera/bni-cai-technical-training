# PBJ GPU Runtime Validation

Run `python scripts/00_environment_check.py --mode cai` inside the target Python 3.10 PBJ GPU session before installing vLLM. The report must show Python 3.10, the expected GPU (NVIDIA L40S in the sandbox, NVIDIA H200 NVL at BNI), a visible CUDA runtime, and a compatible PyTorch build. Pin the tested `torch`, `transformers`, and `vllm` versions only after this check. A driver capability shown by `nvidia-smi` is not the same as the CUDA runtime bundled with PyTorch.

