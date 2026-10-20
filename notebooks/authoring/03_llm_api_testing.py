# %% [markdown]
# # Lab 03: LLM API Testing
#
# **Audience:** Participant
# **Estimated duration:** 30–40 minutes
#
# ## Learning objectives
# By the end you can: explain what you send to a language model and what comes back, read the token usage, see why a request has a size
# limit, receive an answer piece by piece (streaming), see how temperature changes an answer, and handle a busy or failing service.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It finds your group and the shared model address. You do not edit it.
# 2. **Eight steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Hands-on exercise.** You write your own instruction and compare the answer.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. They are safe to run again.
#
# ## Prerequisites
# Complete Lab 00. In `cai` mode this lab needs the shared model address (`VLLM_BASE_URL`, already in your group settings) and an optional
# `VLLM_API_KEY`. In `local` mode a small mock model is started for you and announced.
#
# ## Architecture context
# All ten groups share **one** Qwen3.5-9B model served by vLLM. Your Session only sends small requests; it never starts or downloads the
# model. Because the model is shared, every request has a size limit and a timeout, so one group cannot block the others.

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings, and decides where requests go: the shared model in `cai` mode, or an announced
# mock in `local` mode. You do not need to change anything. It prints your mode and group, never a key or an address.

# %%
# Setup: find the repository, load your group's settings and choose the model endpoint. Nothing to edit.
import json
import os
import sys
import time
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
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
from bni_training.mock_llm import MockOpenAIServer
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
mock_server = MockOpenAIServer(fail_first=1).start() if LAB_MODE == "local" else None
base_url = mock_server.base_url if mock_server else os.environ.get("VLLM_BASE_URL", "")
assert base_url, "VLLM_BASE_URL is required in CAI mode; ask the trainer to validate the shared endpoint."
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id, "endpoint_configured": True})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. What do you send to the model?
# **What it does:** builds the **payload**, the data you send. It holds the model name, a list of messages, and two settings:
# `temperature` (how much the answer may vary) and `max_tokens` (how long the answer may be). Two tables show them.
#
# **Why it matters:** this payload is the whole conversation with the model. Roles decide whose words count more: the `system` message
# sets the rules, the `user` message asks the question.
#
# **Predict first:** which role has the question, and which has the rules?

# %%
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
display(pd.DataFrame(payload["messages"]))
display(pd.DataFrame({"setting": ["model", "temperature", "max_tokens"], "value": [payload["model"], payload["temperature"], payload["max_tokens"]]}))
proved.append("I built a request: messages with roles, a temperature and a token limit")

# %% [markdown]
# ## Step 2. Switch off the model's "thinking"
# **What it does:** adds one extra field to the payload that tells Qwen3.5 not to write its reasoning first.
#
# **Why it matters:** Qwen3.5 normally **thinks** before it answers. That thinking text would use up the small `max_tokens` budget and would
# show internal reasoning to participants. The extra field asks the chat template to skip it. Other models are left unchanged.
#
# **Look for:** the field name in `extra_fields`.

# %%
# Qwen3.5 "thinks" before it answers. Thinking text would consume the small max_tokens budget and would show
# internal reasoning, so we ask the chat template to skip it. Other models are left unchanged.
extras = model_request_extras(payload["model"])
payload.update(extras)
print({"model": payload["model"], "roles": [item["role"] for item in payload["messages"]], "max_tokens": payload["max_tokens"], "extra_fields": sorted(extras)})
proved.append("I switched the model's thinking off with one extra field")

# %% [markdown]
# ## Step 3. Send it, and survive a busy service
# **What it does:** posts the payload with a 30-second timeout and at most **two attempts**. A **429** means the shared queue is busy. A
# **5xx** means the service failed for a moment. In both cases the cell waits briefly and tries once more, then stops.
#
# **Why it matters:** the model is shared, so a polite client never retries without limit. The bounded retry protects everyone's work. In
# `local` mode the mock fails once on purpose, so you can see the retry; the real service usually answers at once.
#
# **Look for:** a line "Attempt 1 ... retrying once" in `local` mode, and a table with the HTTP status and the time taken.

# %%
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
display(pd.DataFrame({"result": ["HTTP status", "attempts used", "seconds"], "value": [response.status_code, attempt, latency_seconds]}))
proved.append("I sent the request with a timeout and a bounded retry")

# %% [markdown]
# ## Step 4. Read the answer and the token count
# **What it does:** pulls the answer text out of `choices` and shows the **usage**: how many tokens went in, how many came out.
#
# **Why it matters:** a **token** is a small piece of text. The model counts input and output in tokens, and the shared service is paced by
# tokens, so usage tells you what a request cost.
#
# **Predict first:** will the output tokens be more or fewer than the `max_tokens` limit of 64?

# %%
answer = visible_answer(body["choices"][0]["message"]["content"])
print("Answer:", answer)
usage = body.get("usage") or {}
display(pd.DataFrame({"tokens": list(usage), "count": list(usage.values())}))
assert answer, "The model returned no text; ask the trainer to check the shared endpoint."
proved.append("I read the answer and the token usage")

# %% [markdown]
# ## Step 5. Stream the answer
# **What it does:** asks again, but receives the answer **piece by piece** while it is written. It records how long the first piece took
# and how long the whole answer took.
#
# **Why it matters:** with streaming the reader sees the first words quickly instead of waiting for the full text. Long answers feel much
# faster, which is why chat tools stream.
#
# **Look for:** `first_piece_s` is smaller than `total_s`. With the local mock both are tiny.

# %%
from bni_training.llm_client import OpenAICompatibleClient

client = OpenAICompatibleClient(base_url, os.getenv("VLLM_API_KEY", "local-placeholder"), payload["model"], extra_body=extras)
pieces, first_piece = [], None
stream_started = time.perf_counter()
for delta in client.stream_chat(payload["messages"], temperature=0.2, max_tokens=64):
    if first_piece is None:
        first_piece = time.perf_counter() - stream_started
    pieces.append(delta)
streamed_answer = visible_answer("".join(pieces))
assert streamed_answer, "The stream contained no text; ask the trainer to inspect the shared endpoint."
print({"pieces": len(pieces), "first_piece_s": round(first_piece, 3), "total_s": round(time.perf_counter() - stream_started, 3)})
print("Streamed answer:", streamed_answer)
proved.append("I streamed an answer and saw the first piece arrive early")

# %% [markdown]
# ## Step 6. Same question, two temperatures
# **What it does:** asks the same question at temperature 0 and at 0.9 and shows both answers.
#
# **Why it matters:** temperature controls variation. At 0 the model picks its most likely words and repeats itself. At a higher value it
# takes more risks, so answers differ from run to run. For reports and numbers you want low values.
#
# **Look for:** whether the two answers differ. The local mock always gives one reply, so there the answers are the same.

# %%
question = [{"role": "user", "content": "Describe a healthy loan portfolio in one short sentence."}]
answers = {}
for temperature in (0.0, 0.9):
    reply = client.chat(question, temperature=temperature, max_tokens=60, timeout=30)
    answers[temperature] = visible_answer(reply["choices"][0]["message"]["content"])
display(pd.DataFrame({"temperature": list(answers), "answer": list(answers.values())}))
assert all(answers.values()), "A request returned no text."
proved.append("I compared the answers at two temperatures")

# %% [markdown]
# ## Step 7. The size limit cuts the answer
# **What it does:** asks for a long answer but allows only **8 tokens**.
#
# **Why it matters:** `max_tokens` is a hard stop. The model is cut off mid-sentence, and the reply says why in `finish_reason`: `length`
# means "stopped because of the limit". Shared work stays bounded, but you must size the limit to the answer you need.
#
# **Look for:** a very short answer, and `finish_reason`.

# %%
long_request = [{"role": "user", "content": "Explain in detail why banks monitor delinquency."}]
cut = client.chat(long_request, temperature=0.0, max_tokens=8, timeout=30)
choice = cut["choices"][0]
print("Cut-off answer:", visible_answer(choice["message"]["content"]))
print("finish_reason:", choice.get("finish_reason"))
print("Output tokens:", (cut.get("usage") or {}).get("completion_tokens"))
proved.append("I saw that max_tokens stops an answer, and how the reply says so")

# %% [markdown]
# ## Hands-on exercise
# Write your own instruction (the `system` message) and temperature, then run the cell and read the answer. Keep the token limit as it is.
#
# - Easy: ask for an answer in exactly one sentence.
# - Medium: ask for the answer as two bullet points.
# - Hard: ask the model to answer as a branch manager, then as a risk analyst, and compare.
#
# **Predict first:** how will your instruction change the answer? The default asks for two short sentences and works as it is.

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
display(pd.DataFrame({"your instruction": [exercise_system_prompt], "temperature": [exercise_temperature], "answer": [exercise_answer]}))
proved.append("I wrote my own instruction and compared the answer")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes your last answer, its token usage and your group id to your group's output folder.
#
# **Why it matters:** the file holds no key, no header and no address, so it is safe to keep and to share with the trainer.

# %%
saved = context.write_output(
    "03_llm_api_result.json",
    json.dumps({"answer": exercise_answer, "usage": exercise_response.get("usage", {}), "group_id": context.group_id}, indent=2),
)
print({"saved": saved.name})
proved.append("I saved a result with no key or address")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Nine lines. A request with roles and limits was sent, thinking was off, the answer and its tokens were read, a stream arrived piece by piece,
# temperature changed an answer, a size limit cut one, and one result file is saved.
#
# ## Common errors
# For 401 or 403, check the key without printing it. For repeated 429, wait: the trainer paces the shared model. For a timeout or a 5xx, ask the
# trainer to check the shared Application. Do not loop without a limit.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. What do the roles, the temperature and `max_tokens` do?
# 2. Why does the request have a timeout and a bounded retry?
# 3. What does streaming give the reader, and what does `finish_reason: length` tell you?
#
# ## Reference implementation
# `bni_training.llm_client` contains the reusable client; `scripts/03_llm_api_testing.py` is the automation reference.
#
# ## Cleanup
# The next cell stops the local mock (if one was started) and closes the data context. The shared model keeps running.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
if mock_server:
    mock_server.stop()
context.close()
lab_status("03", LAB_MODE, passed=len(proved), skipped=1 if LAB_MODE == "local" else 0)
