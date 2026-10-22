# %% [markdown]
# # Demo: Download a Model from Hugging Face
#
# **Audience:** Trainer demo (not one of the 13 participant labs) · **Duration:** 5 minutes
#
# A model on Hugging Face is a folder of files: settings, a tokenizer and the weights. `snapshot_download` copies that folder to
# your disk. A repository often holds the same weights in several formats, so `allow_patterns` picks only the files you need. Here
# that is about 92 MB instead of 977 MB.
#
# The workshop model (Qwen) already lives on shared NFS. Participants never download it, and this demo never touches that folder.
# A gated or private model needs a token in the environment variable `HF_TOKEN`. It is read automatically and never typed into a cell.

# %%
import os
from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ID = os.getenv("DEMO_MODEL_ID", "sentence-transformers/all-MiniLM-L6-v2")  # the model name on Hugging Face
folder = snapshot_download(
    MODEL_ID,
    local_dir=Path.home() / "hf-demo-models" / MODEL_ID.split("/")[-1],  # a new demo folder
    allow_patterns=["*.json", "*.txt", "*.safetensors"],  # only settings, tokenizer text and weights
)
for item in sorted(Path(folder).rglob("*")):
    if item.is_file() and ".cache" not in item.parts:
        print(f"{item.stat().st_size / 1e6:8.2f} MB  {item.relative_to(folder)}")

# %% [markdown]
# ## What to say
# - Look at the list: only a few files, and one large `model.safetensors`. That is the model.
# - If the network blocks the model hub, the cell fails with a connection error. Ask for the hub host to be allowed, or set
#   `HF_ENDPOINT` to an internal mirror.
# - To remove the demo files afterwards, delete the folder `hf-demo-models` in your home folder.
