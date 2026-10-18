# Offline Installation

Build wheels inside the same Linux PBJ Python 3.10 runtime family used by the workshop:

```bash
# One profile per Python environment; profiles are standalone and never layered.
bash scripts/build_wheelhouse.sh --profile participant --output wheelhouse
bash scripts/bootstrap_offline.sh participant
# Another environment (use a separate wheelhouse directory per profile):
bash scripts/build_wheelhouse.sh --profile rag --output wheelhouse-rag
```

Build the GPU profile only after lab 00 has identified a compatible CUDA, PyTorch, Transformers, and vLLM matrix. Do not reuse wheels built on macOS, Windows, a different Python minor version, or a different CUDA profile. Verify `requirements/offline-manifest.json` and all SHA-256 values before transfer.

