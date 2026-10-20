# %% [markdown]
# # Lab 03: LLM API Testing
#
# **Audience:** Participant  
# **Estimated duration:** 30–40 minutes
#
# ## Learning objectives
# Build an OpenAI-compatible payload, make bounded requests, parse choices and usage, stream a response, and recognize friendly 429/5xx handling.
#
# ## Architecture context
# All ten groups share one Qwen3.5-9B vLLM endpoint. Participant CPU Sessions send small requests; they never start or download the model.
#
# ## Prerequisites
# Complete Lab 00. In CAI set `VLLM_BASE_URL` and optional `VLLM_API_KEY`; local mode explicitly starts the repository mock.

# %% [markdown]
# ## Configuration validation
# Resolve the group and execution mode, then choose a real CAI endpoint or an announced local mock. The expected output says which mode is active without printing keys.

# %%
# Load workshop imports, group context, and the explicit local-only mock boundary.
import json
import os
import sys
import time
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
group_env = Path.cwd().parent / "config" / "group.env"
load_group_env(group_env)
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
from bni_training.mock_llm import MockOpenAIServer
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
mock_server = MockOpenAIServer(fail_first=1).start() if LAB_MODE == "local" else None
base_url = mock_server.base_url if mock_server else os.environ.get("VLLM_BASE_URL", "")
assert base_url, "VLLM_BASE_URL is required in CAI mode; ask the trainer to validate the shared endpoint."
print({"mode": LAB_MODE, "group_id": context.group_id, "endpoint_configured": True})

# %% [markdown]
# ## Step-by-step implementation
# Construct the payload visibly. Roles define instruction priority, temperature controls variation, and `max_tokens` bounds shared inference work. Expect a small dictionary without credentials.

# %%
# Build the OpenAI-compatible chat payload participants will send.
from bni_training.llm_client import model_request_extras, visible_answer

payload = {
    "model": os.getenv("VLLM_MODEL", "qwen3.5-9b"),
    "messages": [
        {"role": "system", "content": "You analyze fully synthetic banking data."},
        {"role": "user", "content": "Reply with one short workshop readiness sentence."},
    ],
    "temperature": 0.2,
    "max_tokens": 64,
}
# Qwen3.5 "thinks" before it answers. Thinking text would consume the small max_tokens budget and would show
# internal reasoning, so we ask the chat template to skip it. Other models are left unchanged.
extras = model_request_extras(payload["model"])
payload.update(extras)
print({"model": payload["model"], "roles": [item["role"] for item in payload["messages"]], "max_tokens": 64,
       "extra_fields": sorted(extras)})

# %% [markdown]
# Send with a 30-second timeout and at most two attempts. A 429 means the shared queue is busy; a 5xx means the service failed temporarily. The bounded retry prevents runaway load and should recover from the mock's first 5xx.

# %%
# Post the visible payload with bounded retry and participant-friendly failures.
import httpx

auth_value = os.getenv("VLLM_API_KEY", "local-placeholder")
auth_scheme = "Bearer"
headers = {"Authorization": f"{auth_scheme} {auth_value}"}
request_url = base_url.rstrip("/") + "/chat/completions"
response = None
started = time.perf_counter()
for attempt in range(1, 3):
    response = httpx.post(request_url, json=payload, headers=headers, timeout=30.0)
    if response.status_code not in {429} and response.status_code < 500:
        break
    print(f"Attempt {attempt}: shared service returned {response.status_code}; retrying once.")
    if attempt < 2:
        time.sleep(0.1)
assert response is not None
response.raise_for_status()
latency_seconds = round(time.perf_counter() - started, 3)
body = response.json()
print({"answer": visible_answer(body["choices"][0]["message"]["content"]), "usage": body.get("usage"), "latency_s": latency_seconds})

# %% [markdown]
# Repeat through the reusable client and stream deltas. This keeps parsing visible while showing the convenience boundary. Expect a non-empty concatenated answer.

# %%
# Stream one bounded response from the same configured endpoint.
from bni_training.llm_client import OpenAICompatibleClient

client = OpenAICompatibleClient(
    base_url, os.getenv("VLLM_API_KEY", "local-placeholder"), payload["model"], extra_body=extras
)
streamed_answer = visible_answer("".join(client.stream_chat(payload["messages"], temperature=0.2, max_tokens=64)))
assert streamed_answer, "The stream contained no text; ask the trainer to inspect the shared endpoint."
print({"streamed_answer": streamed_answer})

# %% [markdown]
# ## Hands-on exercise
# Change only the system prompt and temperature, keeping the group configuration and token bound unchanged. The default asks for exactly two sentences and is safe for automated execution.

# %%
# EXERCISE: compare a second small request with a branch-analyst instruction.
exercise_system_prompt = "Answer as a branch analyst in exactly two short sentences."
exercise_temperature = 0.1
exercise_messages = [
    {"role": "system", "content": exercise_system_prompt},
    {"role": "user", "content": "Why should analytical queries be read-only?"},
]
exercise_response = client.chat(exercise_messages, temperature=exercise_temperature, max_tokens=80, timeout=30)
exercise_answer = visible_answer(exercise_response["choices"][0]["message"]["content"])
assert exercise_answer, "No exercise answer was returned."
print({"exercise_temperature": exercise_temperature, "answer": exercise_answer})

# %% [markdown]
# Save a small, credential-free result in the assigned output directory. Expect one JSON filename; no headers or service URL are stored.

# %%
# Persist only safe response fields for the participant checkpoint.
saved = context.write_output(
    "03_llm_api_result.json",
    json.dumps({"answer": exercise_answer, "usage": exercise_response.get("usage", {}), "group_id": context.group_id}, indent=2),
)
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# The raw and streamed calls return text, usage is readable, the first local 5xx is retried once, and a credential-free JSON result is saved.
#
# ## Common errors
# For 401/403 verify the configured key without printing it. For repeated 429 wait for trainer pacing. For timeout or 5xx ask the trainer to check the shared Application; do not loop indefinitely.
#
# ## Completion checkpoint
# Explain the payload roles, temperature, token limit, timeout, and retry bound.
#
# ## Reference implementation
# `bni_training.llm_client` contains the reusable client; `scripts/03_llm_api_testing.py` is the automation reference.
#
# ## Cleanup
# Stop only the local mock and close the local data context. Leave shared vLLM running.

# %%
# Release local resources and print one executor status line.
from bni_training.workshop.notebook_support import lab_status

if mock_server:
    mock_server.stop()
context.close()
lab_status("03", LAB_MODE, passed=5, skipped=1 if LAB_MODE == "local" else 0)
