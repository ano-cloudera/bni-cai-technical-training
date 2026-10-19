# %% [markdown]
# # Lab 09: Phoenix Monitoring
#
# **Audience:** Participant  
# **Estimated duration:** 25 minutes
#
# ## Learning objectives
# Create parent and child spans, attach safe group context, export them to Phoenix, and verify that secret-like attributes are removed.
#
# ## Architecture context
# CPU participant Sessions send OpenTelemetry traces to one shared Phoenix Application. Phoenix is never installed or started by this notebook.
#
# ## Prerequisites
# Complete Lab 08. CAI mode requires `PHOENIX_COLLECTOR_ENDPOINT` and `PHOENIX_UI_URL`; local mode uses an in-memory exporter.

# %% [markdown]
# ## Configuration validation
# Resolve the group and anonymous participant labels. These labels help find a trace but do not create a security boundary.

# %%
# Load the group context and safe participant label without printing credentials or endpoints.
import json
import os
import sys
import time
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
from bni_training.workshop.notebook_support import participant_settings

context = resolve_lab_context(LAB_MODE)
participant = participant_settings()
print({"mode": LAB_MODE, "group_id": context.group_id, "participant_ref": participant.participant_ref})

# %% [markdown]
# ## Step-by-step implementation
# Build a standalone tracer provider. Local execution retains spans in memory; CAI mode additionally exports to the configured shared collector.

# %%
# Configure explicit processors so local and CAI behavior cannot be confused.
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

# %% [markdown]
# Filter attributes before creating spans. The deliberate `api_key` value must disappear, while operational labels remain searchable.

# %%
# Keep only safe trace attributes; never attach credentials to observability data.
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
print({"safe_attribute_names": sorted(trace_attributes)})

# %% [markdown]
# Create one parent span and two children representing SQL and LLM work. OpenInference kinds make the trace structure easy to scan in Phoenix.

# %%
# Emit a small, inspectable trace; no query results or prompts containing secrets are recorded.
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
print({"span_names": [span.name for span in local_spans]})

# %% [markdown]
# Find the trace locally or through the shared Phoenix query API. CAI polling is bounded to three attempts so a busy service never causes an infinite wait.

# %%
# Query only the configured Phoenix UI in CAI mode; local mode reads the in-memory exporter.
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
assert context.group_id in trace_dump and "deliberate-secret" not in trace_dump
print({"trace_found": True, "group_id": context.group_id, "span_count": len(found_spans)})

# %% [markdown]
# ## Hands-on exercise
# Add one allowed teaching attribute to a new span, flush it, and inspect the result. Attribute names should describe operations, not customers or credentials.

# %%
# EXERCISE: change this safe label, then find it in the local span attributes or Phoenix UI.
exercise_attribute = {"workshop.exercise": "trace-search"}
with tracer.start_as_current_span("exercise.lookup", attributes=exercise_attribute):
    pass
provider.force_flush()
assert any(span.attributes.get("workshop.exercise") == "trace-search" for span in memory_exporter.get_finished_spans())
print(exercise_attribute)

# %% [markdown]
# Save only safe identifiers and span names. This checkpoint helps participants compare traces without persisting endpoints or authorization headers.

# %%
# Persist the non-secret trace summary inside the current group workspace.
trace_summary = {
    "group_id": context.group_id,
    "participant_ref": participant.participant_ref,
    "span_names": [span.name for span in memory_exporter.get_finished_spans()],
}
saved = context.write_output("09_trace_summary.json", json.dumps(trace_summary, indent=2))
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# The parent, SQL, and LLM spans are visible; the current group can be found; and the deliberate secret is absent.
#
# ## Common errors
# A timeout means the shared collector or UI is unavailable; retry only through the bounded cell and ask the trainer. A 401/403 means the optional Phoenix credential is wrong.
#
# ## Completion checkpoint
# Explain the parent/child relationship and why `group_id` is useful for search but is not an authorization control.
#
# ## Reference implementation
# `bni_training.observability.safe_trace_attributes` and `scripts/09_phoenix_monitoring.py` contain reusable production checks.
#
# ## Cleanup
# Shut down this notebook-owned tracer provider. Never stop the shared Phoenix Application.

# %%
# Flush pending spans and report one executor status line.
from bni_training.workshop.notebook_support import lab_status

provider.shutdown()
context.close()
lab_status("09", LAB_MODE, passed=7, skipped=1 if LAB_MODE == "local" else 0)
