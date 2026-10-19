# %% [markdown]
# # Lab 12: End-to-End Workshop Portal
#
# **Audience:** Participant  
# **Estimated duration:** 20 minutes
#
# ## Learning objectives
# Connect the notebook concepts to the shared Portal, observe queue states and group locking, and verify a saved group-scoped answer.
#
# ## Architecture context
# All groups use one Streamlit process and exactly one CAI Application replica. Its process-local inference gate defaults to three concurrent model calls, so it must never be scaled out.
#
# ## Prerequisites
# Complete Labs 00 and 03-11. CAI mode requires `WORKSHOP_PORTAL_URL`; local mode creates an in-process Portal with explicit mock services.

# %% [markdown]
# ## Configuration validation
# Resolve the same group, dataset, and mission used by earlier notebooks. The Portal session locks to this group after its first action.

# %%
# Load group context and verify only the presence of the Portal URL variable.
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(os.getenv("BNI_REPO_ROOT", "")) if os.getenv("BNI_REPO_ROOT") else next(
    path for path in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
    if (path / "pyproject.toml").is_file()
)
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
group_env = Path.cwd().parent / "config" / "group.env"
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
portal_url = os.getenv("WORKSHOP_PORTAL_URL", "")
if LAB_MODE == "cai":
    assert portal_url, "WORKSHOP_PORTAL_URL is required in CAI mode. Ask the trainer."
print({"mode": LAB_MODE, "group_id": context.group_id, "portal_url_configured": bool(portal_url)})

# %% [markdown]
# ## Step-by-step implementation
# Check the shared Portal health in CAI mode. Local mode reports the in-process service explicitly instead of pretending it contacted CAI.

# %%
# Probe with a bounded timeout; a failure tells the participant to contact the trainer.
if LAB_MODE == "cai":
    health_url = urllib.parse.urljoin(portal_url.rstrip("/") + "/", "health")
    try:
        with urllib.request.urlopen(health_url, timeout=15) as response:
            portal_health = {"status": response.status, "service": "shared_portal"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Workshop Portal is unreachable: {type(exc).__name__}; ask the trainer") from exc
else:
    portal_health = {"status": 200, "service": "in_process_local"}
print({"portal_health": portal_health})

# %% [markdown]
# In local mode, drive the same `PortalService` used by Streamlit. The visible ticket state, queue statistics, and saved answer connect earlier lessons into one flow.

# %%
# Submit the mission question through a single-process local Portal and collect its result.
from bni_training.workshop.portal.service import GroupLockedError, PortalService

question = context.bundle.sample_questions[0]
local_runtime = tempfile.TemporaryDirectory() if LAB_MODE == "local" else None
service = None
portal_answer = None
queue_states = []
if LAB_MODE == "local":
    service = PortalService.from_env(
        {
            "PORTAL_MODE": "local",
            "WORKSHOP_RUNTIME_DIR": local_runtime.name,
            "PORTAL_ENFORCE_SINGLE_INSTANCE": "false",
            "PORTAL_MAX_RETRIES": "1",
        }
    )
    browser_state = {}
    joined = service.join_group(browser_state, context.group_id)
    state = service.state(browser_state, joined)
    ticket = service.submit_question(state, question)
    queue_states.append({"state": ticket.state.value, **service.gate.stats()})
    assert ticket.wait(60), "The local Portal did not answer within 60 seconds."
    queue_states.append({"state": ticket.state.value, **service.gate.stats()})
    outcome = service.collect(state)
    assert outcome and outcome["state"] == "completed"
    portal_answer = json.loads(service.read_output(joined, outcome["output"]))
print({"user_question": question, "queue_states": queue_states})

# %% [markdown]
# Verify the session lock and answer identity. A locked session cannot switch groups until an explicit reset, and the saved identity must match this notebook context.

# %%
# Prove the local group lock and reject any answer carrying a different group identity.
if LAB_MODE == "local":
    assert state.locked
    other_group = "group_02" if context.group_id != "group_02" else "group_03"
    try:
        service.join_group(browser_state, other_group)
    except GroupLockedError as exc:
        print("Cross-group switch refused:", exc)
    else:
        raise AssertionError("A locked Portal session changed groups unexpectedly.")
    expected_identity = (context.group_id, context.dataset_id, context.mission_id)
    answer_identity = (
        portal_answer["group_id"],
        portal_answer["dataset_id"],
        portal_answer["mission_id"],
    )
    assert answer_identity == expected_identity
print({"group_locked": LAB_MODE == "local" and state.locked, "identity_verified": LAB_MODE == "local"})

# %% [markdown]
# In CAI, open the Portal, select this group, ask the displayed question, and wait for Queued → Processing → Completed. Then this cell reads only this group's output tree.

# %%
# Locate a saved answer without traversing outside the current group workspace.
if LAB_MODE == "cai":
    output_root = (context.workspace / "output").resolve()
    answer_paths = sorted(output_root.glob("*/answer-*.json"))
    assert answer_paths, "Ask the sample question in the Portal first, then rerun this cell."
    selected_answer = answer_paths[-1].resolve()
    assert selected_answer.is_relative_to(output_root), "Refusing an answer outside this group output folder."
    portal_answer = json.loads(selected_answer.read_text(encoding="utf-8"))
    assert portal_answer.get("group_id") == context.group_id
print({"saved_answer_found": bool(portal_answer), "answer_group": portal_answer.get("group_id")})

# %% [markdown]
# Compare the Portal SQL with the hand-built group-bound data path from Lab 05. Both should produce the same read-only semantic plan style for the same question.

# %%
# Re-run only the transparent group-bound query and compare its SQL with the Portal evidence.
reference_sql, reference_result = context.data_tool().bind(context.request()).query(question)
assert portal_answer["sql"].upper().startswith("SELECT")
assert portal_answer["sql"] == reference_sql
assert portal_answer["row_count"] == reference_result.row_count
print({"portal_sql": portal_answer["sql"], "matches_lab_05_path": True})

# %% [markdown]
# ## Hands-on exercise
# Ask a second safe mission question in the Portal and identify its new `answer-NNN.json` file. The automated default validates the first answer so local execution remains deterministic.

# %%
# EXERCISE: in CAI, replace this with another listed mission question and locate its saved file.
exercise_question = context.bundle.sample_questions[0]
assert exercise_question in context.bundle.sample_questions
print({"exercise_question": exercise_question, "current_saved_answer": bool(portal_answer)})

# %% [markdown]
# Save a notebook-side checkpoint containing only the group identity, question, and SQL comparison. The Portal answer itself remains in its session-scoped output directory.

# %%
# Persist a small completion checkpoint in this notebook's assigned workspace.
checkpoint = {
    "group_id": context.group_id,
    "question": question,
    "portal_sql": portal_answer["sql"],
    "matches_reference": portal_answer["sql"] == reference_sql,
}
saved = context.write_output("12_portal_checkpoint.json", json.dumps(checkpoint, indent=2))
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# Portal health is visible, the answer remains in the selected group, queue states are bounded, the group locks after use, and Portal SQL matches the direct semantic path.
#
# ## Common errors
# If health fails, ask the trainer to check the one Portal replica. If no CAI answer exists, ask the sample question in the UI first. A group mismatch must never be bypassed.
#
# ## Completion checkpoint
# Explain how the Portal combines validation, semantic SQL, the shared model queue, group locking, saved outputs, and observability.
#
# ## Reference implementation
# `bni_training.workshop.portal` and `scripts/12_end_to_end_portal.py` contain the reusable Application implementation.
#
# ## Cleanup
# Close only notebook-owned local resources. Never stop or scale the shared Portal Application.

# %%
# Reset local session state, close resources, and report one executor status line.
from bni_training.workshop.notebook_support import lab_status

if service:
    service.reset_session(browser_state)
    service.close()
if local_runtime:
    local_runtime.cleanup()
context.close()
lab_status("12", LAB_MODE, passed=7, skipped=1 if LAB_MODE == "local" else 0)
