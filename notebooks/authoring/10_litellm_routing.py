# %% [markdown]
# # Lab 10: LiteLLM Routing
#
# **Audience:** Participant
# **Estimated duration:** 25 minutes
#
# ## Learning objectives
# By the end you can: explain what a gateway does in front of a model, list the model names it offers (aliases), send the same request
# through two aliases, explain the difference between a retry and a fallback, and see why the key is never printed.
#
# ## How this notebook is organised
# 1. **Service addresses and setup (two cells).** They find the gateway and your group. You do not edit the setup cell.
# 2. **Seven steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Hands-on exercise.** You choose an alias and compare its time.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. Complete Lab 09 first.
#
# ## Prerequisites
# In `cai` mode this lab needs the gateway address (`LITELLM_BASE_URL`, built from the Applications domain in the first cell) and a
# gateway key from your trainer. In `local` mode a mock gateway is started and announced.
#
# ## Architecture context
# One shared **LiteLLM** Application sits in front of the shared vLLM model. Your notebook talks to the gateway, not to the model. The
# gateway gives each model a short name (an **alias**), retries a request that failed for a moment, and can switch to a second route
# (a **fallback**). Keys stay in the environment and are never printed or saved.

# %% [markdown]
# ## Service addresses (fill in once)
# This lab calls a shared service. Its address ends with the **Applications domain**. Ask your trainer for it and paste it between the
# quotes below, **only the domain** (for example `example.apps.company.id`), without the web prefix (the part before `//`) and without a slash at the end. If your
# trainer already set the variable `APPS_DOMAIN`, leave the quotes empty. Nothing secret goes in this cell, and a value that is already set
# elsewhere is never replaced.

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
    os.environ.setdefault("LITELLM_BASE_URL", service_url("bni-litellm-gateway", "/v1"))

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings, and chooses the gateway: the shared one in `cai` mode, an announced mock in
# `local` mode. In `cai` mode, if no key is set in your environment, it asks you to type the key you received; the key is not shown and not
# saved. It prints your mode and group, and only whether a key exists, never its value.

# %%
# Setup: find the repository, load your group's settings and choose the gateway. Nothing to edit.
import json
import sys
import time
from pathlib import Path

import httpx
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
from bni_training.mock_llm import MockOpenAIServer
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
local_gateway = MockOpenAIServer(reply="gateway alias answered").start() if LAB_MODE == "local" else None
gateway_url = local_gateway.base_url if local_gateway else os.getenv("LITELLM_BASE_URL", "")
gateway_key = os.getenv("LITELLM_API_KEY", "local-placeholder")
if LAB_MODE == "cai" and not os.getenv("LITELLM_API_KEY"):
    import getpass

    gateway_key = getpass.getpass("Gateway key from your trainer (not shown, not saved): ").strip()
assert gateway_url, "LITELLM_BASE_URL is required in CAI mode. Fill in the Applications domain in the first cell."
assert gateway_key, "A gateway key is required. Ask your trainer."
headers = {"Authorization": "Bearer" + " " + gateway_key}
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id, "credential_status": "configured"})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. Which models does the gateway offer?
# **What it does:** asks the gateway for its list of models (`GET /models`) and shows them as a table.
#
# **Why it matters:** the names in this list are **aliases**: short names the gateway understands. You always ask for an alias, never for the
# real model file. The gateway decides which real model answers.
#
# **Look for:** `qwen-primary` and `training-fallback`. A 429 means the shared queue is busy; a 5xx means the route is unavailable.

# %%
try:
    models_response = httpx.get(f"{gateway_url.rstrip('/')}/models", headers=headers, timeout=15)
    models_response.raise_for_status()
except httpx.HTTPStatusError as exc:
    hint = "shared queue is busy" if exc.response.status_code == 429 else "gateway route is unavailable"
    raise RuntimeError(f"LiteLLM model listing failed: {hint}") from exc
model_ids = [item["id"] for item in models_response.json().get("data", [])]
assert model_ids
display(pd.DataFrame({"alias offered by the gateway": model_ids}))
proved.append("I listed the aliases the gateway offers")

# %% [markdown]
# ## Step 2. A request with a size limit and a retry
# **What it does:** defines `chat_alias`, a small function that sends one short request to an alias. If the gateway answers 429 (busy) or 5xx
# (failed for a moment), it waits briefly and **tries again, at most twice**.
#
# **Why it matters:** a polite client never retries without limit. A **retry** repeats the **same** route in the hope that it works the next time.
#
# **Look for:** nothing is sent yet. The cell only defines the function.

# %%
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


print("chat_alias is ready: one request, a 32-token limit, a 20-second timeout, at most 3 tries")
proved.append("I defined a request with a size limit, a timeout and a bounded retry")

# %% [markdown]
# ## Step 3. The same request through two aliases
# **What it does:** sends the identical request twice. Only the alias changes: `qwen-primary` and `training-fallback`. The table shows each
# answer and the time it took.
#
# **Why it matters:** the alias is the **only** field that changes, so any difference comes from the route. In this workshop both aliases
# lead to the same shared model, so the answers are alike. In a real setup the second alias could be a smaller or cheaper model.
#
# **Predict first:** will the two answers be the same? Will one be faster?

# %%
rows = []
for alias in ("qwen-primary", "training-fallback"):
    started = time.perf_counter()
    answer = chat_alias(alias)[0]
    rows.append({"alias": alias, "answer": answer, "seconds": round(time.perf_counter() - started, 3)})
alias_results = {row["alias"]: row["answer"] for row in rows}
with pd.option_context("display.max_colwidth", None):
    display(pd.DataFrame(rows))
assert all(row["answer"] for row in rows)
proved.append("I sent the same request through two aliases and compared them")

# %% [markdown]
# ## Step 4. Retry or fallback?
# **What it does:** explains the difference with a table, from what you just used.
#
# **Why it matters:** the two words are easy to mix up. A **retry** asks the **same** route again. A **fallback** gives up on the route and uses a
# **different** one. Retry is for a short hiccup, fallback is for a route that stays down.
#
# **Look for:** which of the two is already in your code.

# %%
display(
    pd.DataFrame(
        {
            "idea": ["retry", "fallback"],
            "what it does": ["asks the same alias again", "switches to another alias"],
            "used when": ["the service failed for a moment (429 or 5xx)", "the first route stays unavailable"],
            "where you saw it": ["inside chat_alias (Step 2)", "the next step"],
        }
    )
)
proved.append("I can explain the difference between a retry and a fallback")

# %% [markdown]
# ## Step 5. A controlled fallback
# **What it does:** tries the primary route first. If it still fails after its retries, it uses **one** approved fallback, and then stops. In
# `local` mode the primary is made to fail on purpose, so you can see the switch. In `cai` mode it uses the two real aliases and does not stop
# any shared service.
#
# **Why it matters:** the fallback is bounded: one primary, one backup, no endless loop.
#
# **Look for:** `selected_route`. In `local` mode it is `training-fallback`. In `cai` mode it is normally `qwen-primary`, because the primary works.

# %%
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
display(pd.DataFrame({"selected_route": [fallback_route], "answer": [fallback_answer]}))
proved.append("I saw a bounded fallback: one primary route and one backup")

# %% [markdown]
# ## Step 6. The key is never shown
# **What it does:** checks that the gateway key is not in anything you are about to save or print, and shows only its length class.
#
# **Why it matters:** a key in a notebook, a log or a trace is a leak. This lab sends the key only in the request header and never prints it.
#
# **Look for:** `key_in_summary: False`.

# %%
summary_text = json.dumps({"aliases": alias_results, "selected_route": fallback_route})
print({"key_in_summary": gateway_key in summary_text, "key_is_set": bool(gateway_key)})
assert gateway_key not in summary_text
proved.append("The key was used in the header only and never appeared in output")

# %% [markdown]
# ## Hands-on exercise
# Choose an alias, run the cell, and compare its time with Step 3. Keep `max_tokens` small, because all groups share one model queue.
#
# - Easy: switch between `qwen-primary` and `training-fallback`.
# - Medium: run it three times and note whether the time changes.
# - Hard: change the user message in `chat_alias` (Step 2) to ask for a different short answer and rerun Step 3.
#
# **Predict first:** which alias will be faster? Only use the two approved aliases. Do not invent a model name.

# %%
# EXERCISE: switch between the two approved aliases; do not invent an upstream model name.
exercise_alias = "qwen-primary"
assert exercise_alias in {"qwen-primary", "training-fallback"}, "Use one of the two approved aliases."
started = time.perf_counter()
exercise_answer, response_headers = chat_alias(exercise_alias)
exercise_latency = round(time.perf_counter() - started, 3)
assert exercise_answer
display(pd.DataFrame({"alias": [exercise_alias], "answer": [exercise_answer], "seconds": [exercise_latency]}))
proved.append("I chose an alias and compared its time")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes the alias answers, the selected route and your latency to your group's output folder.
#
# **Why it matters:** the file holds no key and no header, so it is safe to keep and to share with the trainer.

# %%
routing_summary = {
    "aliases": alias_results,
    "selected_route": fallback_route,
    "exercise_latency_seconds": exercise_latency,
}
saved = context.write_output("10_routing_summary.json", json.dumps(routing_summary, indent=2))
print({"saved": saved.name})
proved.append("I saved a routing summary with no key or header")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Nine lines. The aliases are listed, both returned an answer, a retry and a fallback were told apart, a fallback was bounded, no key was
# displayed or saved, and one summary file is saved.
#
# ## Common errors
# A 429 means wait for the trainer-paced retry window. A 5xx after the bounded retries means the trainer should inspect LiteLLM and vLLM health.
# A 401 means the key is wrong: ask the trainer, and do not print it. A certificate error means the project variables are missing: ask the trainer.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. What is an alias, and why do you ask for an alias and not for the real model?
# 2. What is the difference between a retry and a fallback?
# 3. Why does the lab bound both, and why is the key never printed?
#
# ## Reference implementation
# `scripts/10_litellm_routing.py` and `config/litellm.yaml` contain the reusable route definition.
#
# ## Cleanup
# The next cell stops only the local mocks that this notebook started. Never stop the shared LiteLLM Application.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
for server in (failed_primary, fallback_server, local_gateway):
    if server:
        server.stop()
context.close()
lab_status("10", LAB_MODE, passed=len(proved), skipped=1 if LAB_MODE == "local" else 0)
