# %% [markdown]
# # Lab 01: Model Artifact Validation
#
# **Audience:** Trainer only  
# **Estimated duration:** 20–30 minutes  
# **TRAINER ONLY:** Participants may read this notebook but must not manage model weights.
#
# ## Learning objectives
# Inspect a Qwen model directory, validate the required files, and relate artifact metadata to vLLM settings.
#
# ## Architecture context
# One Qwen3.5-9B BF16 artifact lives on CAI NFS and is shared by one H200-backed vLLM Application. Model weights are never packaged in this repository.
#
# ## Prerequisites
# Use Python 3.10. In CAI, set `WORKSHOP_ROLE=trainer` and `MODEL_PATH`. Local mode uses a temporary synthetic stand-in and performs no download.

# %% [markdown]
# ## Configuration validation
# This cell finds the repository, loads the small notebook helpers, and validates the execution mode. It expects to print Python and mode information without exposing credentials.

# %%
# Locate repository imports and validate the trainer execution mode.
import json
import os
import sys
import tempfile
from pathlib import Path

def _repo_root() -> Path:
    # A generated group workspace records the repository in config/group.env, so no setup is needed.
    env_file = Path.cwd().parent / "config" / "group.env"
    saved = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line) if env_file.is_file() else {}
    if os.getenv("BNI_REPO_ROOT") or saved.get("BNI_REPO_ROOT"):
        return Path(os.getenv("BNI_REPO_ROOT") or saved["BNI_REPO_ROOT"])
    found = [p for p in (Path.cwd().resolve(), *Path.cwd().resolve().parents) if (p / "pyproject.toml").is_file()]
    assert found, "Open this notebook from a generated group workspace, or set BNI_REPO_ROOT."
    return found[0]


ROOT = _repo_root()
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
ROLE = os.getenv("WORKSHOP_ROLE", "participant").lower()
assert LAB_MODE in {"local", "cai"}, "LAB_MODE must be local or cai"
ACTIVE = LAB_MODE == "local" or ROLE == "trainer"
print({"python": sys.version.split()[0], "mode": LAB_MODE, "trainer_only": True, "active": ACTIVE})

# %% [markdown]
# ## Step-by-step implementation
# The trainer selects the NFS path through `MODEL_PATH`. Local execution creates only a tiny temporary stand-in so the validation flow is testable without model downloads. The expected output is a path label and no production data.

# %%
# Select the configured NFS artifact or a disposable local teaching artifact.
from bni_training.model_artifact import directory_manifest, validate_model_path

temporary_model = None
if LAB_MODE == "local":
    temporary_model = tempfile.TemporaryDirectory(prefix="workshop-model-")
    model_path = Path(temporary_model.name)
    (model_path / "config.json").write_text(
        json.dumps({"architectures": ["Qwen3ForCausalLM"], "torch_dtype": "bfloat16"})
    )
    (model_path / "tokenizer.json").write_text("{}")
    (model_path / "model-00001-of-00001.safetensors").write_bytes(b"synthetic-training-placeholder")
elif ACTIVE:
    assert os.getenv("MODEL_PATH"), "MODEL_PATH is required for the trainer in CAI mode"
    model_path = Path(os.environ["MODEL_PATH"])
else:
    model_path = None
print({"artifact_source": "local stand-in" if LAB_MODE == "local" else "MODEL_PATH environment"})

# %% [markdown]
# The validation checks `config.json` and at least one `.safetensors` shard before hashing files. This protects the deployment step from an incomplete copy. Expect a compact manifest with relative names, sizes, and checksums.

# %%
# Validate required files and build a checksum manifest without changing the artifact.
manifest = []
metadata = {}
if ACTIVE:
    validated_path = validate_model_path(model_path)
    metadata = json.loads((validated_path / "config.json").read_text())
    manifest = directory_manifest(validated_path)
    print({"files": len(manifest), "bytes": sum(item["size"] for item in manifest)})
    print({"architecture": metadata.get("architectures"), "dtype": metadata.get("torch_dtype")})
else:
    print("SKIPPED: trainer role is required in CAI mode; no model files were opened.")

# %% [markdown]
# ## Hands-on exercise
# Change `exercise_required_suffix` to another safe artifact suffix and rerun. The default checks that at least one weights shard exists and prints matching relative names.

# %%
# EXERCISE: compare a safe file-list rule with the validated manifest.
exercise_required_suffix = ".safetensors"
exercise_matches = [item["path"] for item in manifest if item["path"].endswith(exercise_required_suffix)]
if ACTIVE:
    assert exercise_matches, "No matching artifact found; inspect MODEL_PATH before deployment."
print({"exercise_suffix": exercise_required_suffix, "matching_files": exercise_matches})

# %% [markdown]
# ## Expected result
# The manifest includes `config.json`, tokenizer metadata when present, and one or more safetensors shards. Local mode clearly labels its synthetic stand-in.
#
# ## Common errors
# A missing `MODEL_PATH`, absent `config.json`, or missing safetensors shard means the trainer must repair the NFS artifact. Do not add download code to this notebook.
#
# ## Completion checkpoint
# Explain why validation happens before vLLM starts and why checksums are optional for a large shared artifact.
#
# ## Reference implementation
# The reusable validation functions live in `bni_training.model_artifact`; the automation reference is `scripts/01_model_artifact_validation.py`.
#
# ## Cleanup
# Local mode removes its temporary stand-in below. In CAI, leave the shared NFS artifact unchanged.

# %%
# Report the executor contract and release only the disposable local directory.
from bni_training.workshop.notebook_support import lab_status

if temporary_model is not None:
    temporary_model.cleanup()
lab_status("01", LAB_MODE, passed=3 if ACTIVE else 0, skipped=0 if ACTIVE else 1)
