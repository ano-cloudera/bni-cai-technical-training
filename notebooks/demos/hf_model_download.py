# %% [markdown]
# # Demo: Download a Model from Hugging Face
#
# **Audience:** Trainer demo (not one of the 13 participant labs)
# **Estimated duration:** 10 minutes
#
# ## Learning objectives
# By the end you can: look inside a model repository before downloading it, download only the files you need, check that the
# download is complete, load the model once to prove it works, and explain what to do when the network blocks the model hub.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It names the model and the folder. A small model is used on purpose.
# 2. **Four steps.** Preview, download, verify, use. Each step says what the next cell does and why.
# 3. **Hands-on exercise.** Change the file filter and watch the size change.
# 4. **Clean up and closing.**
#
# ## Prerequisites
# The `huggingface_hub` package in the kernel, and network access to the model hub (or an internal mirror). A **gated** or private model also
# needs a token in the environment variable `HF_TOKEN`. Never type a token into a cell.
#
# ## Architecture context
# A model on the hub is a **repository**: a folder of files (settings, a tokenizer, and the weights). `snapshot_download` copies that
# folder to a local directory. The weights are the large part, and one repository often holds the same weights in several formats, so
# you choose which files to take. In this workshop the real model (Qwen) already lives on shared NFS. Participants never download it,
# and this notebook never touches that folder.

# %% [markdown]
# ## Setup
# **What it does:** names the model, the target folder and the file filter, then checks that `huggingface_hub` is installed.
#
# **Why it matters:** the folder is a new, separate demo folder, never the vLLM model folder. The filter (`ALLOW`) is the list of file
# patterns to take: settings, tokenizer text and `safetensors` weights.
#
# **Look for:** the model name, the target folder, the library version, and `token_set` (only says yes or no; the token is never shown).

# %%
import fnmatch
import json
import os
import shutil
import time
from pathlib import Path

import pandas as pd
from IPython.display import display

MODEL_ID = os.getenv("DEMO_MODEL_ID", "sentence-transformers/all-MiniLM-L6-v2")
DEMO_ROOT = Path(os.getenv("DEMO_MODEL_DIR", Path.home() / "hf-demo-models"))
TARGET = DEMO_ROOT / MODEL_ID.replace("/", "__")
ALLOW = ["*.json", "*.txt", "*.safetensors"]
HF_TOKEN = os.getenv("HF_TOKEN")  # only for gated or private models; it is passed to the hub and never printed

try:
    import huggingface_hub
except ImportError as exc:
    raise RuntimeError("huggingface_hub is not installed in this kernel. Use the rag or participant profile.") from exc
print({"model_id": MODEL_ID, "target_folder": TARGET.name, "huggingface_hub": huggingface_hub.__version__, "token_set": bool(HF_TOKEN)})

# %% [markdown]
# ## Step-by-step implementation
#
# ## Step 1. Look inside the repository first
# **What it does:** asks the hub for the list of files in the repository and their sizes, without downloading any of them. It marks
# the files that match `ALLOW` and adds up their size.
#
# **Why it matters:** repositories are often much larger than the model you need. Checking first avoids filling a disk or waiting for
# gigabytes you will not use.
#
# **Predict first:** how many of the files will be downloaded, and how many megabytes? Then read the numbers.
#
# **If it fails:** the message names the reason. A timeout or a refused connection usually means the network or proxy blocks the model
# hub. Ask for the hub host to be allowed, or set `HF_ENDPOINT` to an internal mirror.

# %%
from huggingface_hub import HfApi

api = HfApi(token=HF_TOKEN)
try:
    info = api.model_info(MODEL_ID, files_metadata=True)
except Exception as exc:
    raise RuntimeError(
        "Cannot read the model repository (" + type(exc).__name__ + "). Check the network, ask for the model hub host "
        "to be allowed by the proxy, or set HF_ENDPOINT to an internal mirror. A gated model also needs HF_TOKEN."
    ) from exc
files = pd.DataFrame(
    [
        {
            "file": item.rfilename,
            "MB": round((item.size or 0) / 1e6, 2),
            "will download": any(fnmatch.fnmatch(item.rfilename, pattern) for pattern in ALLOW),
        }
        for item in info.siblings
    ]
)
display(files.sort_values("MB", ascending=False).head(12))
print(
    {
        "files_in_repository": len(files),
        "MB_in_repository": float(round(files["MB"].sum(), 1)),
        "files_to_download": int(files["will download"].sum()),
        "MB_to_download": float(round(files.loc[files["will download"], "MB"].sum(), 1)),
    }
)

# %% [markdown]
# ## Step 2. Download only what you need
# **What it does:** copies the files that match `ALLOW` to the target folder with `snapshot_download`, and prints how long it took.
# If the folder already holds some of the files, they are reused.
#
# **Why it matters:** `allow_patterns` is what keeps the download small. The token, if you set one, goes to the hub and is not printed.
#
# **Look for:** a number of seconds and the same folder name as in the setup cell.

# %%
from huggingface_hub import snapshot_download

started = time.perf_counter()
local_path = snapshot_download(repo_id=MODEL_ID, local_dir=TARGET, allow_patterns=ALLOW, token=HF_TOKEN)
print({"folder": Path(local_path).name, "seconds": round(time.perf_counter() - started, 1)})

# %% [markdown]
# ## Step 3. Check that the download is complete
# **What it does:** lists every downloaded file with its size, reads `config.json`, and checks that a weights file is present.
#
# **Why it matters:** a model folder without weights loads without an error until you use it. Checking the files now saves a confusing
# failure later.
#
# **Look for:** a `*.safetensors` file in the table and a `model_type` in the printed settings.

# %%
downloaded = sorted(path for path in TARGET.rglob("*") if path.is_file() and ".cache" not in path.parts)
display(
    pd.DataFrame(
        {
            "file": [str(path.relative_to(TARGET)) for path in downloaded],
            "MB": [round(path.stat().st_size / 1e6, 2) for path in downloaded],
        }
    )
)
config = json.loads((TARGET / "config.json").read_text(encoding="utf-8"))
print({key: config.get(key) for key in ("model_type", "hidden_size", "num_hidden_layers", "vocab_size")})
assert any(path.suffix == ".safetensors" for path in downloaded), (
    "No safetensors weights were downloaded. If the repository only has .bin weights, add '*.bin' to ALLOW and run Step 2 again."
)

# %% [markdown]
# ## Step 4. Use the model once
# **What it does:** loads the folder with `sentence-transformers` and turns two sentences into vectors. This only works for an
# embedding model such as the default one. If the library is missing, or the model is a different kind, the cell says it was skipped.
#
# **Why it matters:** loading it from the local folder proves that the files work without the internet.
#
# **Look for:** a shape such as `(2, 384)`: two sentences, 384 numbers each.

# %%
try:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(TARGET), device="cpu")
    vectors = model.encode(["What is a non-performing loan?", "Total outstanding by risk band"])
    print({"vectors_shape": tuple(vectors.shape)})
except ImportError:
    print("SKIPPED: sentence-transformers is not installed in this kernel.")
except Exception as exc:
    print("SKIPPED: this folder is not a sentence-transformers model (" + type(exc).__name__ + ").")

# %% [markdown]
# ## Hands-on exercise
# Change the file filter and see how the size changes. Do this in Step 1 and look at `MB_to_download` before you download anything.
#
# - Easy: set `DEMO_MODEL_ID` to another small model and run Step 1 again. Read the size first.
# - Medium: add `"*.onnx"` to `ALLOW` in the setup cell and run Step 1. How many megabytes does it add?
# - Hard: download one file only. Call `hf_hub_download(repo_id=MODEL_ID, filename="config.json", local_dir=TARGET)`.
#
# **Predict first:** which pattern adds the most megabytes? Only download a large model on purpose, after you have read its size.

# %%
# EXERCISE: change ALLOW or DEMO_MODEL_ID, then run Step 1 again to see the new size before downloading.
print({"ALLOW": ALLOW})

# %% [markdown]
# ## Clean up
# **What it does:** deletes the demo folder when `CLEAN_UP` is `True`. It never deletes anything else.
#
# **Why it matters:** model files take space. Remove them when the demo is over.

# %%
CLEAN_UP = False  # set to True to delete the demo folder
if CLEAN_UP:
    assert TARGET.parent == DEMO_ROOT, "Refusing to delete a folder outside the demo root."
    shutil.rmtree(TARGET, ignore_errors=True)
    print({"deleted": TARGET.name})
else:
    print({"kept": TARGET.name, "hint": "set CLEAN_UP = True to delete it"})

# %% [markdown]
# ## Expected result
# Step 1 shows that only a small part of the repository is needed. Step 2 downloads it in a few seconds. Step 3 lists the files and a
# `safetensors` weights file. Step 4 prints a vector shape, or says it was skipped.
#
# ## Common errors
# - `Cannot read the model repository`: the network or proxy blocks the model hub, or the model name is wrong. Ask for the hub host to be
#   allowed, or set `HF_ENDPOINT` to an internal mirror.
# - A message about access or authorization: the model is gated or private. Set `HF_TOKEN` in the environment, not in a cell.
# - `No safetensors weights were downloaded`: the repository only has `.bin` weights. Add `*.bin` to `ALLOW`.
# - No space left: preview first (Step 1) and choose a smaller filter.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. Why do you look at the file list before you download?
# 2. What does `allow_patterns` change, and why does it matter for size?
# 3. Why does the real workshop model stay on shared NFS and never go through a notebook?
#
# ## Where this fits in the workshop
# The Qwen model and the embedding model are placed on shared storage by the trainer. Participants do not download models, and the
# weights are never packaged with the repository. This demo shows the same idea on a small model so you can explain it.
