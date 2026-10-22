# %% [markdown]
# # Lab 12: End-to-End Workshop Portal
#
# **Audience:** Participant
# **Estimated duration:** 20 minutes
#
# ## Learning objectives
# By the end you can: use the shared Portal as an end user, read its queue states, see why your group is locked after the first question, find your
# saved answer, and prove that the Portal and your own notebook produce the same SQL for the same question.
#
# ## How this notebook is organised
# 1. **Service addresses and setup (two cells).** They find the Portal and your group. You do not edit the setup cell.
# 2. **Seven steps.** Each step says what the next cell does and why, you run it, and you read what it prints. In `cai` mode, **Step 2 asks you to use the
#    Portal in your browser** before the notebook can read your answer.
# 3. **Hands-on exercise.** You ask a second question in the Portal.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. Complete Labs 00 and 03 to 11 first.
#
# ## Prerequisites
# In `cai` mode this lab needs the Portal address (`WORKSHOP_PORTAL_URL`, built from the Applications domain in the first cell) and **one question already
# asked in the Portal** for your group. In `local` mode an in-process Portal with explicit mock services is used.
#
# ## Architecture context
# All groups use **one** Streamlit Portal and exactly **one** replica. It lets only three model calls run at the same time (a process-local gate), so it is
# never scaled out. When you ask a question it moves through the states **Queued, Processing, Completed**, and its answer is saved in your group's own
# folder. After your first question the session is **locked** to your group.

# %% [markdown]
# ## Service addresses (fill in once)
# This lab calls a shared service. Its address ends with the **Applications domain**. Ask your trainer for it and paste it between the quotes below,
# **only the domain** (for example `example.apps.company.id`), without the web prefix (the part before `//`) and without a slash at the end. If your trainer already set the
# variable `APPS_DOMAIN`, leave the quotes empty. Nothing secret goes in this cell, and a value that is already set elsewhere is never replaced.

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
    os.environ.setdefault("WORKSHOP_PORTAL_URL", service_url("bni-workshop-portal"))

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings, and resolves the same group, dataset and mission as the earlier notebooks. It prints your
# group and whether the Portal address is set, never the address.

# %%
# Setup: find the repository and load your group's settings. Nothing to edit.
import json
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
from IPython.display import display

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

# Values already set in the Session environment win over config/group.env.
group_env = Path.cwd().parent / "config" / "group.env"
load_group_env(group_env)
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
portal_url = os.getenv("WORKSHOP_PORTAL_URL", "")
if LAB_MODE == "cai":
    assert portal_url, "WORKSHOP_PORTAL_URL is required in CAI mode. Fill in the Applications domain in the first cell."
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id, "portal_url_configured": bool(portal_url)})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. Is the Portal alive?
# **What it does:** in `cai` mode, calls the Portal's health address with a 15-second limit. In `local` mode it reports that the service runs inside this
# notebook, and does not pretend to contact CAI.
#
# **Why it matters:** if the one Portal replica is down, nothing later can work. A failure here tells you to contact the trainer.
#
# **Look for:** `status: 200`.

# %%
if LAB_MODE == "cai":
    health_url = urllib.parse.urljoin(portal_url.rstrip("/") + "/", "health")
    try:
        with urllib.request.urlopen(health_url, timeout=15) as response:
            portal_health = {"status": response.status, "service": "shared_portal"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Workshop Portal is unreachable: {type(exc).__name__}; ask the trainer") from exc
else:
    portal_health = {"status": 200, "service": "in_process_local"}
display(pd.DataFrame({"check": list(portal_health), "value": list(portal_health.values())}))
proved.append("The Portal answered its health check")

# %% [markdown]
# ## Step 2. Ask the question
# **What it does:** shows the question you will ask. In `local` mode the notebook asks it itself through the same `PortalService` the Streamlit app
# uses. In `cai` mode **you** ask it: open the Portal in your browser, choose your group, click the sample question shown below, and wait until it
# shows **Completed**.
#
# **Why it matters:** this is the whole workshop in one request: your question is checked, turned into SQL, queued for the shared model, answered and saved.
#
# **Do this in `cai` mode:** ask the question in the Portal first. Step 5 reads the answer the Portal saved.

# %%
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
    queue_states.append({"moment": "just submitted", "state": ticket.state.value, **service.gate.stats()})
    assert ticket.wait(60), "The local Portal did not answer within 60 seconds."
    queue_states.append({"moment": "after the answer", "state": ticket.state.value, **service.gate.stats()})
    outcome = service.collect(state)
    assert outcome and outcome["state"] == "completed"
    portal_answer = json.loads(service.read_output(joined, outcome["output"]))
print("Question to ask in the Portal:", question)
proved.append("I know the question to ask in the Portal")

# %% [markdown]
# ## Step 3. The queue states
# **What it does:** in `local` mode, shows the ticket state and the gate numbers just after the question was submitted and after it was answered. In
# `cai` mode, tells you what to watch in the browser.
#
# **Why it matters:** the Portal lets only three model calls run at once. A request moves **Queued** (waiting for a free slot), **Processing** (the model
# is working) and **Completed**. If too many people ask together you may see **Busy** or **Timed out**: that is the gate protecting the shared model.
#
# **Look for:** a state that changes from the first row to the second.

# %%
if LAB_MODE == "local":
    display(pd.DataFrame(queue_states))
else:
    display(
        pd.DataFrame(
            {
                "what you see in the Portal": ["Queued", "Processing", "Completed", "Busy / Timed out"],
                "meaning": ["waiting for a free slot (3 at a time)", "the shared model is working", "answer and SQL are shown", "the gate protected the model; try again"],
            }
        )
    )
proved.append("I can read the queue states Queued, Processing and Completed")

# %% [markdown]
# ## Step 4. Your group is locked
# **What it does:** in `local` mode, tries to switch the same session to another group and shows that it is refused. It also checks that the saved answer
# carries your group, dataset and mission. In `cai` mode, tells you where to see the lock in the Portal.
#
# **Why it matters:** after the first question the session is locked to your group, so one browser cannot ask questions as two groups. Changing group needs an
# explicit reset. This is a workshop rule, not a security boundary.
#
# **Look for:** a line "Cross-group switch refused" in `local` mode. In `cai` mode, the Portal sidebar says "Locked to ... for this session".

# %%
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
    lock_report = {"group_locked": state.locked, "identity_verified": True}
else:
    lock_report = {"group_locked": "see the Portal sidebar", "identity_verified": "checked in Step 5"}
display(pd.DataFrame({"check": list(lock_report), "result": list(lock_report.values())}))
proved.append("My session is locked to my group after the first question")

# %% [markdown]
# ## Step 5. Find your saved answer
# **What it does:** in `cai` mode, looks only inside **your group's own output folder** for the answer file the Portal wrote
# (`output/<session>/answer-NNN.json`), checks that it belongs to your group, and shows it. In `local` mode the answer is already in memory.
#
# **Why it matters:** answers are stored per group. The code refuses any file outside your folder and any answer carrying another group's identity.
#
# **Look for:** a table with your group, the SQL, and the number of rows. If it says "Ask the sample question in the Portal first", go back to Step 2.

# %%
if LAB_MODE == "cai":
    output_root = (context.workspace / "output").resolve()
    answer_paths = sorted(output_root.glob("*/answer-*.json"))
    assert answer_paths, "Ask the sample question in the Portal first, then rerun this cell."
    saved_answers = [json.loads(path.read_text(encoding="utf-8")) for path in answer_paths if path.resolve().is_relative_to(output_root)]
    saved_answers = [item for item in saved_answers if item.get("group_id") == context.group_id]
    assert saved_answers, "No saved answer belongs to your group. Ask the sample question in the Portal, then rerun this cell."
    # Prefer the newest answer to the sample question; otherwise the newest answer of any question.
    portal_answer = next((item for item in reversed(saved_answers) if item.get("question") == question), saved_answers[-1])
    assert portal_answer.get("group_id") == context.group_id
with pd.option_context("display.max_colwidth", None):
    display(
        pd.DataFrame(
            {
                "field": ["group_id", "mission_id", "row_count", "sql"],
                "value": [portal_answer.get(key) for key in ("group_id", "mission_id", "row_count", "sql")],
            }
        )
    )
proved.append("I found my group's saved answer and it belongs to my group")

# %% [markdown]
# ## Step 6. Portal SQL equals your SQL
# **What it does:** runs the same question through your own group-bound data path from Lab 05 and compares its SQL and row count with what the Portal saved.
#
# **Why it matters:** this is the proof that the Portal and your notebook follow the same rules. The Portal adds a queue and a model; it does not change the SQL.
#
# **Look for:** `sql_matches: True` and `rows_match: True`.

# %%
# Compare with the question the Portal actually answered, so a different question asked earlier cannot cause a false mismatch.
answered_question = portal_answer.get("question") or question
reference_sql, reference_result = context.data_tool().bind(context.request()).query(answered_question)
assert portal_answer["sql"].upper().startswith("SELECT")
assert portal_answer["sql"] == reference_sql
assert portal_answer["row_count"] == reference_result.row_count
print({"sql_matches": portal_answer["sql"] == reference_sql, "rows_match": portal_answer["row_count"] == reference_result.row_count})
proved.append("The Portal's SQL equals the SQL of my own Lab 05 path")

# %% [markdown]
# ## Step 7. Every answer you have so far
# **What it does:** lists the answer files saved for your group (`cai` mode) or the one local answer, with the question time order.
#
# **Why it matters:** each question you ask in the Portal adds a new numbered file. This is where you will find the answer of your own question in the exercise.
#
# **Look for:** one row per answer file.

# %%
if LAB_MODE == "cai":
    files = [str(path.relative_to(output_root)) for path in sorted(output_root.glob("*/answer-*.json"))]
else:
    files = ["(local mode: the answer was kept in memory)"]
display(pd.DataFrame({"saved answer file": files}))
proved.append("I listed the answers saved for my group")

# %% [markdown]
# ## Hands-on exercise
# Ask a **second** safe question in the Portal and find its new `answer-NNN.json` file.
#
# - Easy: ask another question from the list below, then rerun Step 7 and see one more file.
# - Medium: open the new file's SQL in Step 5 by changing `answer_paths[-1]` to the new file and compare it with the first one.
# - Hard: ask a question that is **not** on the list and read what the Portal says.
#
# **Predict first:** which of your tables will the SQL of the second question use? In `local` mode the default checks the first answer so the run stays
# repeatable. In `cai` mode, replace `exercise_question` with another listed question.

# %%
# EXERCISE: in CAI, replace this with another listed mission question and locate its saved file.
exercise_question = context.bundle.sample_questions[0]
assert exercise_question in context.bundle.sample_questions, "Choose a question from the list of your mission."
display(pd.DataFrame({"questions you may ask": list(context.bundle.sample_questions)}))
print({"exercise_question": exercise_question, "current_saved_answer": bool(portal_answer)})
proved.append("I chose a second question to ask in the Portal")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes your group, the question and the SQL comparison to your group's output folder. The Portal's own answer stays in its session folder.
#
# **Why it matters:** the file holds only identities and SQL. No key and no address.

# %%
checkpoint = {
    "group_id": context.group_id,
    "question": question,
    "portal_sql": portal_answer["sql"],
    "matches_reference": portal_answer["sql"] == reference_sql,
}
saved = context.write_output("12_portal_checkpoint.json", json.dumps(checkpoint, indent=2))
print({"saved": saved.name})
proved.append("I saved a checkpoint with the SQL comparison")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Nine lines. The Portal is healthy, you know the queue states, your session is locked to your group, your saved answer is found and belongs to your
# group, the Portal's SQL equals your own SQL, and one checkpoint file is saved.
#
# ## Common errors
# If health fails, ask the trainer to check the one Portal replica. If no answer exists in `cai` mode, ask the sample question in the Portal first and rerun
# Step 5. A group mismatch must never be bypassed.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. What happens to a question between Queued and Completed?
# 2. Why is your session locked to one group, and why is that not a security boundary?
# 3. Why must the Portal's SQL equal the SQL of your own notebook?
#
# ## Reference implementation
# `bni_training.workshop.portal` and `scripts/12_end_to_end_portal.py` contain the reusable Application implementation.
#
# ## Cleanup
# The next cell resets the local session, closes only this notebook's own resources and the data engine. Never stop or scale the shared Portal.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
if service:
    service.reset_session(browser_state)
    service.close()
if local_runtime:
    local_runtime.cleanup()
context.close()
lab_status("12", LAB_MODE, passed=len(proved), skipped=1 if LAB_MODE == "local" else 0)
