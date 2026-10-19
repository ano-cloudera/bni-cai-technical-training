# %% [markdown]
# # Lab 00: Environment Validation
#
# **Audience:** Trainer and participant  
# **Estimated duration:** 10–15 minutes
#
# ## Learning objectives
# Validate Python 3.10, group and participant context, the synthetic dataset assignment, service configuration, and a writable output folder.
#
# ## Architecture context
# One physical dataset serves ten logical groups. The default `PARTICIPANT_MODE=group_driver` uses one CPU Session per group; `individual_learning` is optional after CAI capacity validation.
#
# ## Prerequisites
# Open the notebook inside the repository or a generated group workspace. CAI mode requires `GROUP_ID`, `DATASET_ID`, `MISSION_ID`, and `GROUP_WORKSPACE` from `group.env`.

# %% [markdown]
# ## Configuration validation
# This bootstrap locates the installed workshop code and validates local versus CAI mode. Expect Python and mode labels; it does not print secrets or service URLs.

# %%
# Locate the repository and validate the notebook execution mode.
import os
import sys
from pathlib import Path

ROOT = Path(os.getenv("BNI_REPO_ROOT", "")) if os.getenv("BNI_REPO_ROOT") else next(
    path for path in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
    if (path / "pyproject.toml").is_file()
)
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
assert LAB_MODE in {"local", "cai"}, "LAB_MODE must be local or cai"
group_env = Path.cwd().parent / "config" / "group.env"
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
print({"python": sys.version.split()[0], "mode": LAB_MODE, "group_env_found": bool(os.getenv("GROUP_ENV_FILE"))})

# %% [markdown]
# ## Step-by-step implementation
# Resolve the group assignment and anonymous participant label. `PARTICIPANT_REF` is a runtime label, never a CAI signed-in identity. Expect group, dataset, mission, and mode names.

# %%
# Resolve validated group context and anonymous participant settings.
from bni_training.workshop.lab_context import resolve_lab_context
from bni_training.workshop.notebook_support import participant_settings

context = resolve_lab_context(LAB_MODE)
participant = participant_settings()
print(context.describe())
print({"PARTICIPANT_MODE": participant.mode, "PARTICIPANT_REF": participant.participant_ref})
assert context.group_id.startswith("group_")
assert participant.participant_ref.startswith("participant_")

# %% [markdown]
# Inspect only the assigned logical bundle. The cell reports table names and file presence, not local paths. Expect non-empty synthetic CSV files for every allowed table.

# %%
# Confirm the group's mission and its allowed synthetic CSV tables.
bundle = context.bundle
csv_checks = {
    table: (bundle.csv_dir / f"{table}.csv").is_file() and (bundle.csv_dir / f"{table}.csv").stat().st_size > 0
    for table in bundle.tables
}
assert all(csv_checks.values()), "An assigned synthetic CSV file is missing; ask the trainer to validate data/raw."
print({"GROUP_ID": context.group_id, "DATASET_ID": bundle.dataset_id, "MISSION_ID": bundle.mission_id})
print({"mission": bundle.mission_title, "allowed_tables": list(bundle.tables), "csv_ready": csv_checks})

# %% [markdown]
# Shared service locations must come from six environment variables. This cell prints presence only so internal URLs and optional authentication never appear in notebook output.

# %%
# Check service-variable presence without exposing URL or authentication values.
service_variables = (
    "VLLM_BASE_URL",
    "QDRANT_URL",
    "PHOENIX_COLLECTOR_ENDPOINT",
    "PHOENIX_UI_URL",
    "LITELLM_BASE_URL",
    "WORKSHOP_PORTAL_URL",
)
service_presence = {name: bool(os.getenv(name)) for name in service_variables}
print(service_presence)
if LAB_MODE == "cai":
    assert service_presence["VLLM_BASE_URL"], "VLLM_BASE_URL is required before participant hands-on."

# %% [markdown]
# ## Hands-on exercise
# Review the mission and allowed tables, then write and read one harmless checkpoint in your assigned output directory. The default label is safe in either participant mode.

# %%
# EXERCISE: change only this anonymous checkpoint label and rerun the cell.
exercise_label = participant.participant_ref
checkpoint_text = f"{context.group_id}:{exercise_label}:{context.mission_id}\n"
checkpoint_path = context.write_output("00_environment_checkpoint.txt", checkpoint_text)
assert checkpoint_path.read_text() == checkpoint_text
print({"checkpoint": checkpoint_path.name, "driver_or_participant": exercise_label})

# %% [markdown]
# ## Expected result
# Python is 3.10 in the target CAI runtime, the correct group mission and allowed tables appear, service variables are reported by presence, and the checkpoint round trip passes. GPU checks are intentionally absent from participant CPU Sessions.
#
# ## Common errors
# If CAI mode lacks group values or `VLLM_BASE_URL`, reload the generated `group.env` or ask the trainer. Never paste a token into a notebook cell.
#
# ## Completion checkpoint
# State your group id, mission, participant mode, and which shared services are needed in later labs.
#
# ## Reference implementation
# Context validation lives in `bni_training.workshop.lab_context`; `scripts/00_environment_validation.py` is the automation reference.
#
# ## Cleanup
# Keep the small checkpoint as training evidence. Close the local data context; do not stop any shared Application.

# %%
# Close local resources and print exactly one executor status line.
from bni_training.workshop.notebook_support import lab_status

context.close()
lab_status("00", LAB_MODE, passed=5, skipped=1)
