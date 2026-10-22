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
# ## Service addresses (fill in once)
# This lab calls shared services. All of their addresses end with the same **Applications domain**. Ask your trainer for it and paste it
# between the quotes below. If your trainer already set the variable `APPS_DOMAIN`, leave the quotes empty. Nothing secret goes in
# this cell, and a value that is already set elsewhere is never replaced.

# %%
import os

# Trust the platform's certificate authority if the project did not set it. A value that is already set is never replaced.
_ca_file = "/etc/ssl/certs/ca-certificates.crt"
if os.path.isfile(_ca_file):
    os.environ.setdefault("SSL_CERT_FILE", _ca_file)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_file)

APPS_DOMAIN = ""  # paste the Applications domain from your trainer between the quotes
APPS_DOMAIN = APPS_DOMAIN or os.getenv("APPS_DOMAIN", "")
APPS_DOMAIN = APPS_DOMAIN.strip().split("://")[-1].strip("/")  # also accepts a pasted address


def service_url(app, path="", port=""):
    """The address of a shared Application: its name, the domain you pasted above, an optional port and path."""
    from urllib.parse import urlunsplit

    return urlunsplit(("https", f"{app}.{APPS_DOMAIN}{port}", path, "", ""))
if APPS_DOMAIN:
    os.environ.setdefault("QDRANT_URL", service_url("bni-qdrant", port=":443"))
    os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", service_url("bni-phoenix", "/v1/traces"))
    os.environ.setdefault("PHOENIX_UI_URL", service_url("bni-phoenix"))
    os.environ.setdefault("LITELLM_BASE_URL", service_url("bni-litellm-gateway", "/v1"))
    os.environ.setdefault("WORKSHOP_PORTAL_URL", service_url("bni-workshop-portal"))
# Workshop constants: CSV is the data backend and the shared model needs no key (a placeholder, not a secret).
os.environ.setdefault("DATA_MODE", "csv")
os.environ.setdefault("VLLM_API_KEY", "EMPTY")
RUNTIME_PROFILE = ""  # ask your trainer for the profile name, or leave empty if it is already set
if RUNTIME_PROFILE:
    os.environ.setdefault("RUNTIME_PROFILE", RUNTIME_PROFILE)

# %% [markdown]
# ## Configuration validation
# This bootstrap locates the installed workshop code and validates local versus CAI mode. Expect Python and mode labels; it does not print secrets or service URLs.

# %%
# Locate the repository and validate the notebook execution mode.
import os
import sys
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
from bni_training.workshop.notebook_support import load_group_env

# A generated workspace provides config/group.env (LAB_MODE, GROUP_ID, GROUP_WORKSPACE, VLLM_BASE_URL, VLLM_MODEL).
# Values already set in the Session environment win. No manual setup is needed.
load_group_env(Path.cwd().parent / "config" / "group.env")
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
