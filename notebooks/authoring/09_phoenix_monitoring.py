# %% [markdown]
# # Lab 09: Phoenix Monitoring
#
# **Audience:** Participant
# **Estimated duration:** 25 minutes
#
# ## Learning objectives
# By the end you can: explain what a trace and a span are, record a parent span with two child spans, see that a secret is
# removed before anything is sent, find your trace in Phoenix, and add an attribute of your own.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It finds your group and your anonymous participant label. You do not edit it.
# 2. **Eight steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Hands-on exercise.** You add one attribute to a new span.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. Phoenix is shared and already running; this notebook never installs or starts it.
#
# ## Prerequisites
# Complete Lab 08. In `cai` mode this lab needs `PHOENIX_COLLECTOR_ENDPOINT` (where traces are sent) and `PHOENIX_UI_URL` (where they
# are read back). In `local` mode an in-memory exporter is used instead.
#
# ## Architecture context
# A **trace** is the record of one piece of work, step by step, with timing. Each step is a **span**. A span can have **child**
# spans, like a stopwatch with smaller stopwatches inside it. Your Session sends its spans to one shared **Phoenix** Application, which
# shows them in a web page. Labels such as your `group_id` make a trace easy to find, but they are not a security control.

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
    os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", service_url("bni-phoenix", "/v1/traces"))
    os.environ.setdefault("PHOENIX_UI_URL", service_url("bni-phoenix"))

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings, and prints your group and your anonymous participant label
# (`participant_01` to `participant_04`). You do not need to change anything. It never prints a credential or an endpoint.

# %%
# Setup: find the repository and load your group's settings. Nothing to edit.
import json
import os
import sys
import time
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
from bni_training.workshop.notebook_support import participant_settings

context = resolve_lab_context(LAB_MODE)
participant = participant_settings()
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id, "participant_ref": participant.participant_ref})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. Where do the spans go?
# **What it does:** builds a tracer. Every span is kept in memory so you can read it here. In `cai` mode the same spans are also sent
# to the shared Phoenix collector.
#
# **Why it matters:** the tracer is the camera. Nothing is recorded until you create one, and you decide where the pictures go.
#
# **Look for:** `export` says `shared_phoenix` in `cai` mode and `in_memory` in `local` mode.

# %%
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

PROJECT = "bni-credit-insight-lab09"
provider = TracerProvider(resource=Resource.create({"openinference.project.name": PROJECT}))
memory_exporter = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
collector = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "")
if LAB_MODE == "cai":
    assert collector, "PHOENIX_COLLECTOR_ENDPOINT is required in CAI mode. Ask the trainer."
    headers = {"Authorization": "Bearer" + " " + os.environ["PHOENIX_API_KEY"]} if os.getenv("PHOENIX_API_KEY") else None
    provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=collector, headers=headers)))
tracer = provider.get_tracer("bni-training.lab09")
print({"export": "shared_phoenix" if collector else "in_memory", "project": PROJECT})
proved.append("I built a tracer that keeps spans and sends them to Phoenix")

# %% [markdown]
# ## Step 2. Remove secrets before anything is sent
# **What it does:** takes a set of labels that includes a deliberately fake `api_key`, and passes them through `safe_trace_attributes`.
# A table shows which labels would be sent.
#
# **Why it matters:** traces are stored and shared. A credential that reaches a trace is a leak, so the filter runs **before** a span is created.
#
# **Predict first:** which label will be dropped? Then read the table.

# %%
from bni_training.observability import safe_trace_attributes

raw_attributes = {
    "group_id": context.group_id,
    "dataset_id": context.dataset_id,
    "mission_id": context.mission_id,
    "participant_ref": participant.participant_ref,
    "api_key": "deliberate-" + "secret-that-must-be-dropped",
}
trace_attributes = safe_trace_attributes(raw_attributes)
assert "api_key" not in trace_attributes
display(pd.DataFrame({"label": list(raw_attributes), "sent to Phoenix?": [name in trace_attributes for name in raw_attributes]}))
proved.append("A secret-like label was removed before the trace was created")

# %% [markdown]
# ## Step 3. Record a trace
# **What it does:** creates one **parent** span (`workshop.analysis`) with two **child** spans: `sql.query` (a tool) and `llm.chat` (a model call).
# Then it lists the spans in a table with their kind, their parent and how long each took.
#
# **Why it matters:** this is the same shape as a real request: a question comes in, data is read, a model answers. The kind
# (`CHAIN`, `TOOL`, `LLM`) lets Phoenix draw each step differently.
#
# **Look for:** the `parent` column. The two children name the parent span.

# %%
with tracer.start_as_current_span("workshop.analysis", attributes=trace_attributes) as parent_span:
    parent_span.set_attribute("openinference.span.kind", "CHAIN")
    with tracer.start_as_current_span("sql.query") as sql_span:
        sql_span.set_attribute("openinference.span.kind", "TOOL")
        sql_span.set_attribute("db.operation", "SELECT")
    with tracer.start_as_current_span("llm.chat") as llm_span:
        llm_span.set_attribute("openinference.span.kind", "LLM")
        llm_span.set_attribute("llm.request.max_tokens", 80)
provider.force_flush()
local_spans = memory_exporter.get_finished_spans()
assert {span.name for span in local_spans} >= {"workshop.analysis", "sql.query", "llm.chat"}
names_by_id = {span.context.span_id: span.name for span in local_spans}
display(
    pd.DataFrame(
        [
            {
                "span": span.name,
                "kind": span.attributes.get("openinference.span.kind"),
                "parent": names_by_id.get(span.parent.span_id) if span.parent else "(none, this is the parent)",
                "milliseconds": round((span.end_time - span.start_time) / 1e6, 3),
            }
            for span in local_spans
        ]
    )
)
proved.append("I recorded a parent span with two child spans")

# %% [markdown]
# ## Step 4. Check the parent and child relationship
# **What it does:** checks in code that both child spans really point to the parent.
#
# **Why it matters:** the parent-child link is what turns a pile of spans into one readable trace. Without it Phoenix would show three
# unrelated dots.
#
# **Look for:** `True` twice.

# %%
parent_id = next(span.context.span_id for span in local_spans if span.name == "workshop.analysis")
for child_name in ("sql.query", "llm.chat"):
    child = next(span for span in local_spans if span.name == child_name)
    print(f"{child_name} is a child of workshop.analysis:", child.parent is not None and child.parent.span_id == parent_id)
    assert child.parent is not None and child.parent.span_id == parent_id
proved.append("Both child spans point to the parent")

# %% [markdown]
# ## Step 5. Find the trace
# **What it does:** looks for your trace. In `cai` mode it asks the shared Phoenix for the spans of this lab and tries up to three times,
# because Phoenix may need a moment to receive them. In `local` mode it reads the in-memory spans.
#
# **Why it matters:** sending a trace is only half the job. Finding it again proves the whole path works: your notebook, the
# collector and the Phoenix storage.
#
# **Look for:** `trace_found: True` and a span count above zero.

# %%
if LAB_MODE == "local":
    found_spans = [{"name": span.name, "attributes": dict(span.attributes)} for span in local_spans]
else:
    phoenix_ui = os.getenv("PHOENIX_UI_URL", "")
    assert phoenix_ui, "PHOENIX_UI_URL is required in CAI mode. Ask the trainer."
    project_name = urllib.parse.quote(PROJECT)
    url = f"{phoenix_ui.rstrip('/')}/v1/projects/{project_name}/spans?limit=100"
    request_headers = {"Authorization": "Bearer" + " " + os.environ["PHOENIX_API_KEY"]} if os.getenv("PHOENIX_API_KEY") else {}
    found_spans = []
    for attempt in range(3):
        with urllib.request.urlopen(urllib.request.Request(url, headers=request_headers), timeout=15) as response:
            found_spans = json.load(response).get("data", [])
        if context.group_id in json.dumps(found_spans, default=str):
            break
        time.sleep(attempt + 1)
trace_dump = json.dumps(found_spans, default=str)
assert context.group_id in trace_dump, "Your trace was not found yet; wait a few seconds and run this cell again."
print({"trace_found": True, "group_id": context.group_id, "span_count": len(found_spans)})
proved.append("I found my trace again")

# %% [markdown]
# ## Step 6. Is the secret really gone?
# **What it does:** searches everything Phoenix returned for the fake secret from Step 2.
#
# **Why it matters:** removing the label in Step 2 only counts if it also never arrived. Check the result, not the intention.
#
# **Look for:** `secret_in_trace: False`.

# %%
secret_in_trace = "deliberate-secret" in trace_dump
print({"secret_in_trace": secret_in_trace})
assert not secret_in_trace
proved.append("The deliberate secret never reached Phoenix")

# %% [markdown]
# ## Step 7. Why group_id is in the trace
# **What it does:** counts how many of the returned spans carry your `group_id`.
#
# **Why it matters:** the label helps you (and the trainer) search for your own traces among everyone's. It is a **label for finding**, not a lock:
# separation between groups in this workshop is an application rule, not a security boundary.
#
# **Look for:** a count above zero.

# %%
mine = [span for span in found_spans if context.group_id in json.dumps(span, default=str)]
print({"spans_with_my_group_id": len(mine), "spans_returned": len(found_spans)})
assert mine
proved.append("I used group_id as a label to find my own spans")

# %% [markdown]
# ## Hands-on exercise
# Add one label of your own to a new span, then find it in the table. Choose a name that describes an operation, not a customer or a
# credential.
#
# - Easy: change the value `trace-search` to another word.
# - Medium: change the label name too, for example `workshop.step`.
# - Hard: run `safe_trace_attributes({"workshop.exercise": "x", "api_key": "y"})` in a new cell and see which label survives.
#
# **Predict first:** will your label appear in the span list? Keep the label name starting with `workshop.` so you can find it.

# %%
# EXERCISE: change this safe label, then find it in the local span attributes or Phoenix UI.
exercise_attribute = {"workshop.exercise": "trace-search"}
with tracer.start_as_current_span("exercise.lookup", attributes=exercise_attribute):
    pass
provider.force_flush()
exercise_spans = [span for span in memory_exporter.get_finished_spans() if span.name == "exercise.lookup"]
assert any(all(span.attributes.get(key) == value for key, value in exercise_attribute.items()) for span in exercise_spans)
display(pd.DataFrame([{"span": span.name, **dict(span.attributes)} for span in exercise_spans]))
proved.append("I added a label of my own to a span")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes your group, your participant label and the span names to your group's output folder.
#
# **Why it matters:** the file holds only safe identifiers. It contains no endpoint and no authorization header, so you can compare traces later.

# %%
trace_summary = {
    "group_id": context.group_id,
    "participant_ref": participant.participant_ref,
    "span_names": [span.name for span in memory_exporter.get_finished_spans()],
}
saved = context.write_output("09_trace_summary.json", json.dumps(trace_summary, indent=2))
print({"saved": saved.name})
proved.append("I saved a trace summary with no endpoint or header")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Nine lines. The parent and its two children are visible, the children point to the parent, your trace is found, your group id is searchable,
# and the deliberate secret is absent.
#
# ## Common errors
# A timeout means the shared collector or the Phoenix page is unavailable; retry only through the bounded cell (Step 5) and ask the trainer. A
# 401 or 403 means the optional Phoenix credential is wrong. If the trace is not found at once, wait a few seconds and run Step 5 again.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. What is the difference between a trace and a span, and what does the parent-child link add?
# 2. Why are labels filtered before the span is created?
# 3. Why is `group_id` useful for search but not an authorization control?
#
# ## Reference implementation
# `bni_training.observability.safe_trace_attributes` and `scripts/09_phoenix_monitoring.py` contain reusable production checks.
#
# ## Cleanup
# The next cell flushes pending spans and shuts down this notebook's own tracer. Never stop the shared Phoenix Application.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
provider.shutdown()
context.close()
lab_status("09", LAB_MODE, passed=len(proved), skipped=1 if LAB_MODE == "local" else 0)
