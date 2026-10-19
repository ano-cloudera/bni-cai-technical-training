# %% [markdown]
# # Lab 02: vLLM Deployment and Validation
#
# **Audience:** Trainer demo  
# **Estimated duration:** 30–45 minutes  
# **TRAINER ONLY:** Participants use the endpoint from CPU Sessions; they never start vLLM.
#
# ## Learning objectives
# Read the proposed vLLM command, validate OpenAI-compatible routes, and compare safe generation parameters.
#
# ## Architecture context
# One Qwen3.5-9B server runs BF16 with tensor parallel size 1 on one H200. The Application must already be running before participant notebook 03 begins.
#
# ## Prerequisites
# In CAI, set `WORKSHOP_ROLE=trainer`, `MODEL_PATH`, `VLLM_BASE_URL`, and optional authentication variables. Local mode uses an explicit in-process mock and requests no GPU.

# %% [markdown]
# ## Configuration validation
# This cell loads the repository, validates `LAB_MODE`, and checks the trainer gate. It prints only variable presence, never authentication values.

# %%
# Locate repository imports and validate non-secret trainer configuration.
import os
import shlex
import sys
from pathlib import Path

ROOT = next(
    path for path in (Path.cwd().resolve(), *Path.cwd().resolve().parents)
    if (path / "pyproject.toml").is_file()
)
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
ROLE = os.getenv("WORKSHOP_ROLE", "participant").lower()
assert LAB_MODE in {"local", "cai"}, "LAB_MODE must be local or cai"
ACTIVE = LAB_MODE == "local" or ROLE == "trainer"
print({"mode": LAB_MODE, "trainer_only": True, "url_configured": bool(os.getenv("VLLM_BASE_URL"))})

# %% [markdown]
# ## Step-by-step implementation
# `build_vllm_command` exposes every deployment argument as text. The notebook never executes this command. Expect BF16, TP=1, bounded sequence length, and the configured model path.

# %%
# Build a reviewable launch command; do not start the production server here.
from bni_training.model_artifact import build_vllm_command

model_path = os.getenv("MODEL_PATH", "${MODEL_PATH}")
served_model = os.getenv("VLLM_MODEL", "qwen3.5-9b")
launch_command = build_vllm_command(model_path, served_model, int(os.getenv("VLLM_PORT", "8000")))
assert launch_command[:2] == ["python", "-m"] and launch_command[2].endswith("api_server")
assert launch_command[launch_command.index("--tensor-parallel-size") + 1] == "1"
assert launch_command[launch_command.index("--dtype") + 1] == "bfloat16"
print("Application command preview:", shlex.join(launch_command))
print("This command is displayed only; start the CAI Application through the trainer workflow.")

# %% [markdown]
# The endpoint comes only from `VLLM_BASE_URL`. Local mode announces and starts a deterministic mock; CAI mode refuses a missing URL instead of silently mocking. Expect a model id from `/v1/models`.

# %%
# Connect to the existing endpoint with an explicit local-only mock boundary.
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.mock_llm import MockOpenAIServer

mock_server = None
if LAB_MODE == "local":
    mock_server = MockOpenAIServer().start()
    base_url = mock_server.base_url
    print("LOCAL MODE: using the explicit workshop mock; GPU launch is SKIPPED.")
elif ACTIVE:
    assert os.getenv("VLLM_BASE_URL"), "VLLM_BASE_URL is required in CAI mode"
    base_url = os.environ["VLLM_BASE_URL"].rstrip("/")
else:
    base_url = ""
client = OpenAICompatibleClient(base_url, os.getenv("VLLM_API_KEY", "local-not-secret"), served_model) if ACTIVE else None

# %% [markdown]
# The health and chat calls use short, trainer-paced requests. `max_tokens` bounds shared GPU work and the client timeout prevents an endless wait. Expect HTTP health, `/v1/models`, response text, and usage metadata.

# %%
# Validate health, model discovery, and one bounded OpenAI-compatible request.
if ACTIVE:
    assert client.server_health() == 200
    models_response = client.health()
    messages = [{"role": "user", "content": "Reply with one short workshop readiness sentence."}]
    response = client.chat(messages, temperature=0.1, max_tokens=64, timeout=30)
    answer = response["choices"][0]["message"]["content"]
    print({"models": [item["id"] for item in models_response["data"]]})
    print({"answer": answer, "usage": response.get("usage", {})})
else:
    print("SKIPPED: trainer role is required in CAI mode; no request was sent.")

# %% [markdown]
# ## Hands-on exercise
# Change only `exercise_max_tokens` or `exercise_temperature`. Keep the request short so one shared endpoint stays responsive. The default values are safe for automated execution.

# %%
# EXERCISE: compare a second safe inference setting against the first response.
exercise_max_tokens = 48
exercise_temperature = 0.2
exercise_answer = ""
if ACTIVE:
    exercise_response = client.chat(
        [{"role": "user", "content": "Name one benefit of a shared inference endpoint."}],
        temperature=exercise_temperature,
        max_tokens=exercise_max_tokens,
        timeout=30,
    )
    exercise_answer = exercise_response["choices"][0]["message"]["content"]
    assert exercise_answer, "The endpoint returned no text; ask the trainer to inspect vLLM logs."
print({"max_tokens": exercise_max_tokens, "temperature": exercise_temperature, "answer": exercise_answer})

# %% [markdown]
# ## Expected result
# The command preview shows BF16 and TP=1, model discovery returns an id, and both bounded requests return text. Local mode reports the GPU step as skipped.
#
# ## Common errors
# A timeout, 401/403, 429, or 5xx response should be reported to the trainer. Never print the API key and never restart the shared Application from this notebook.
#
# ## Completion checkpoint
# Explain why participant Sessions stay CPU-only and how `max_tokens` affects shared inference capacity.
#
# ## Reference implementation
# Reusable command and client code lives in `bni_training.model_artifact` and `bni_training.llm_client`; `scripts/02_vllm_deployment.py` is the automation reference.
#
# ## Cleanup
# Stop only the explicit local mock. Leave the shared vLLM Application running for participants.

# %%
# Release the local mock and print exactly one notebook executor status line.
from bni_training.workshop.notebook_support import lab_status

if mock_server is not None:
    mock_server.stop()
lab_status("02", LAB_MODE, passed=4 if ACTIVE else 0, skipped=1 if LAB_MODE == "local" or not ACTIVE else 0)
