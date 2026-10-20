# %% [markdown]
# # Lab 10: LiteLLM Routing
#
# **Audience:** Participant  
# **Estimated duration:** 25 minutes
#
# ## Learning objectives
# Inspect gateway models, compare two aliases, and observe bounded retry followed by a controlled fallback.
#
# ## Architecture context
# One shared LiteLLM Application routes requests to the shared vLLM endpoint. Participant keys and upstream credentials remain in environment variables.
#
# ## Prerequisites
# Complete Lab 09. CAI mode requires `LITELLM_BASE_URL`; local mode uses explicit mock endpoints.

# %% [markdown]
# ## Configuration validation
# Resolve group context and start local-only endpoints. The key is reported only as configured or absent, never partially printed.

# %%
# Select the explicit local mock or the shared CAI gateway.
import json
import os
import sys
import time
from pathlib import Path

import httpx

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
group_env = Path.cwd().parent / "config" / "group.env"
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
from bni_training.mock_llm import MockOpenAIServer
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
local_gateway = MockOpenAIServer(reply="gateway alias answered").start() if LAB_MODE == "local" else None
gateway_url = local_gateway.base_url if local_gateway else os.getenv("LITELLM_BASE_URL", "")
gateway_key = os.getenv("LITELLM_API_KEY", "local-placeholder")
assert gateway_url, "LITELLM_BASE_URL is required in CAI mode. Ask the trainer."
print({"mode": LAB_MODE, "group_id": context.group_id, "credential_status": "configured" if gateway_key else "absent"})

# %% [markdown]
# ## Step-by-step implementation
# List the aliases exposed by the gateway. A 429 means the shared queue is busy; a 5xx means the trainer should check the route.

# %%
# Call the OpenAI-compatible models endpoint with an explicit timeout.
headers = {"Authorization": "Bearer" + " " + gateway_key}
try:
    models_response = httpx.get(f"{gateway_url.rstrip('/')}/models", headers=headers, timeout=15)
    models_response.raise_for_status()
except httpx.HTTPStatusError as exc:
    hint = "shared queue is busy" if exc.response.status_code == 429 else "gateway route is unavailable"
    raise RuntimeError(f"LiteLLM model listing failed: {hint}") from exc
model_ids = [item["id"] for item in models_response.json().get("data", [])]
assert model_ids
print({"available_models": model_ids})

# %% [markdown]
# Build the same bounded request for two teaching aliases. The alias is the only payload field that changes, making routing behavior visible.

# %%
# Send one short request per alias with at most two retries on 429 or 5xx.
def chat_alias(alias: str, base_url: str = gateway_url, retries: int = 2) -> tuple[str, dict]:
    payload = {
        "model": alias,
        "messages": [{"role": "user", "content": "Return the active route name."}],
        "temperature": 0.0,
        "max_tokens": 32,
    }
    for attempt in range(retries + 1):
        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=headers, timeout=20
        )
        if response.status_code not in {429, 500, 502, 503, 504}:
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"], dict(response.headers)
        if attempt < retries:
            time.sleep(0.1 * (attempt + 1))
    raise RuntimeError(f"Alias {alias} remained busy or unavailable after {retries + 1} attempts")

alias_results = {alias: chat_alias(alias)[0] for alias in ("qwen-primary", "training-fallback")}
print({"alias_results": alias_results})

# %% [markdown]
# Demonstrate controlled fallback. Local mode forces the primary to fail; CAI mode uses the configured aliases without stopping shared infrastructure.

# %%
# Try the primary route first, then one approved fallback; there is no unbounded loop.
failed_primary = MockOpenAIServer(fail_first=3).start() if LAB_MODE == "local" else None
fallback_server = MockOpenAIServer(reply="fallback route answered").start() if LAB_MODE == "local" else None
primary_url = failed_primary.base_url if failed_primary else gateway_url
fallback_url = fallback_server.base_url if fallback_server else gateway_url
try:
    fallback_route, fallback_answer = "qwen-primary", chat_alias("qwen-primary", primary_url)[0]
except RuntimeError:
    fallback_route = "training-fallback"
    fallback_answer = chat_alias("training-fallback", fallback_url)[0]
assert fallback_answer
print({"selected_route": fallback_route, "answer": fallback_answer})

# %% [markdown]
# ## Hands-on exercise
# Choose an alias for a short response and compare its elapsed time. Keep `max_tokens` small because all groups share one model queue.

# %%
# EXERCISE: switch between the two approved aliases; do not invent an upstream model name.
exercise_alias = "qwen-primary"
started = time.perf_counter()
exercise_answer, response_headers = chat_alias(exercise_alias)
exercise_latency = round(time.perf_counter() - started, 3)
assert exercise_answer
print({"alias": exercise_alias, "latency_seconds": exercise_latency, "header_names": sorted(response_headers)[:5]})

# %% [markdown]
# Save route names, latency, and answers without saving the gateway key or authorization header.

# %%
# Persist a credential-free routing checkpoint.
routing_summary = {
    "aliases": alias_results,
    "selected_route": fallback_route,
    "exercise_latency_seconds": exercise_latency,
}
saved = context.write_output("10_routing_summary.json", json.dumps(routing_summary, indent=2))
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# Both aliases return an answer, fallback is bounded and visible, and no key value is displayed or saved.
#
# ## Common errors
# A 429 means wait for the trainer-paced retry window. A 5xx after the bounded retries means the trainer should inspect LiteLLM and vLLM health.
#
# ## Completion checkpoint
# Explain the difference between a model alias, an upstream model, retry, and fallback.
#
# ## Reference implementation
# `scripts/10_litellm_routing.py` and `config/litellm.yaml` contain the reusable route definition.
#
# ## Cleanup
# Stop only notebook-owned local mocks. Never stop the shared LiteLLM Application.

# %%
# Release local resources and report one executor status line.
from bni_training.workshop.notebook_support import lab_status

for server in (failed_primary, fallback_server, local_gateway):
    if server:
        server.stop()
context.close()
lab_status("10", LAB_MODE, passed=6, skipped=1 if LAB_MODE == "local" else 0)
