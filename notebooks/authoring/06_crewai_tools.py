# %% [markdown]
# # Lab 06: CrewAI Tools
#
# **Audience:** Participant
# **Estimated duration:** 45–60 minutes
#
# ## Learning objectives
# By the end you can: explain what an AI agent is, give it one tool that can only read your group's data, watch it use that
# tool, see a forged group identity refused, and change the agent's goal to see how its answer changes.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It opens your group's data tool and connects the model. You do not edit it.
# 2. **Seven steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Your turn.** You change the agent's goal and compare two answers.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. Complete Labs 03 to 05 first.
#
# ## Prerequisites
# Complete Labs 03 to 05. In `cai` mode this lab needs the shared model endpoint (`VLLM_BASE_URL`).
#
# ## Architecture context
# An **agent** is a language model with a role, a goal, and tools it may call. Here the only tool reads your group's data. It
# is bound to one validated request, so the agent cannot choose another group or another table. In `cai` mode the model is
# the shared vLLM endpoint; in `local` mode a clearly labelled mock answers instead.

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings, opens the data tool and connects CrewAI to the model. You do not
# need to change anything. It prints your group and the mode, and never a credential.

# %%
# Setup: find the repository, load your group's settings and connect the model. Nothing to edit.
import json
import os
import sys
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
from bni_training.labs import crewai_llm
from bni_training.mock_llm import MockOpenAIServer
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
mock_server = MockOpenAIServer(reply="The tool result is summarised without changing its facts.").start() if LAB_MODE == "local" else None
base_url = mock_server.base_url if mock_server else os.environ.get("VLLM_BASE_URL", "")
assert base_url, "VLLM_BASE_URL is required in CAI mode."
crew_llm = crewai_llm(base_url, os.getenv("VLLM_API_KEY", "local-placeholder"))
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id, "mission_id": context.mission_id})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. Ask the data yourself first
# **What it does:** asks the sample question of your mission directly through the group-bound data tool, with no agent, and
# shows the result as a table.
#
# **Why it matters:** this is the ground truth. Later you compare it with what the agent reports, so you can tell whether the
# agent really used the data or invented an answer.
#
# **Predict first:** what columns do you expect?

# %%
question = context.bundle.sample_questions[0]
hand_sql, hand_result = context.data_tool().bind(context.request()).query(question)
print("Question:", question)
print("SQL:", hand_sql)
display(pd.DataFrame(hand_result.rows, columns=hand_result.columns))
proved.append("I asked the data myself, so I know the true answer")

# %% [markdown]
# ## Step 2. Give the agent a tool
# **What it does:** wraps the same data tool with CrewAI's `@tool`. The tool takes only a `question`. There is no parameter for a
# group, a dataset or a table. A `RecordingDataTool` notes every call so you can check later what the agent really did.
#
# **Why it matters:** the agent can only do what its tools allow. Because the group is fixed inside the tool, a clever prompt
# cannot make it read another group's data.
#
# **Look for:** the tool name and the group it is bound to.

# %%
from crewai.tools import tool
from bni_training.crew import RecordingDataTool

recording_tool = RecordingDataTool(context.data_tool().bind(context.request()))

@tool("query_group_banking_data")
def query_group_banking_data(question: str) -> str:
    """Query approved synthetic banking metrics for the current group only."""
    sql, result = recording_tool.query(question)
    return json.dumps(
        {"sql": sql, "columns": list(result.columns), "rows": result.rows[:25], "row_count": result.row_count},
        default=str,
    )

print({"tool": query_group_banking_data.name, "bound_group": context.group_id, "calls so far": len(recording_tool.calls)})
proved.append("I gave an agent one tool that can only read my group's data")

# %% [markdown]
# ## Step 3. Define the agent
# **What it does:** creates the analyst agent with a role, a goal and a backstory, the model, and the one tool.
#
# **Why it matters:** these four lines of text are all that steers the agent. Changing the goal changes how it behaves. You do
# that in "Your turn".
#
# **Look for:** exactly one tool in the agent's tool list.

# %%
from crewai import Agent, Crew, Process, Task

analyst_agent = Agent(
    role="Synthetic Banking Analyst",
    goal="Use the approved tool for grounded mission facts",
    backstory="You analyze only the synthetic dataset assigned to this workshop group.",
    llm=crew_llm,
    tools=[query_group_banking_data],
    verbose=False,
)
display(pd.DataFrame({"field": ["role", "goal", "tools"], "value": [analyst_agent.role, analyst_agent.goal, ", ".join(item.name for item in analyst_agent.tools)]}))
assert len(analyst_agent.tools) == 1
proved.append("I defined an agent with a role, a goal and exactly one tool")

# %% [markdown]
# ## Step 4. Let the agent work
# **What it does:** gives the agent a task that requires the tool, runs it, then prints the answer. `kickoff_blocking` is used
# because JupyterLab already runs an event loop. In `cai` mode this calls the real model, so it can take up to a minute.
#
# **Why it matters:** this is the whole idea of an agent: you state a task, and the model decides to call the tool.
#
# **Predict first:** how many times will the agent call the tool?

# %%
from bni_training.crew import kickoff_blocking

analysis_task = Task(
    description="Answer the participant question: {question}. You must use the data tool.",
    expected_output="A concise answer grounded in the tool rows",
    agent=analyst_agent,
)
crew = Crew(agents=[analyst_agent], tasks=[analysis_task], process=Process.sequential, verbose=False)
crew_output = kickoff_blocking(crew, {"question": question})
assert recording_tool.calls, "The agent did not call the data tool; inspect its goal and task."
print("Answer:", str(crew_output))
print("Tool calls:", len(recording_tool.calls))
proved.append("My agent called the data tool and answered")

# %% [markdown]
# ## Step 5. Did the agent use the data?
# **What it does:** shows every tool call the agent made (the question it sent, the SQL, the number of rows), next to the SQL you got
# by hand in Step 1.
#
# **Why it matters:** an answer is only trustworthy if it comes from a real tool call. The recorded SQL is your evidence.
#
# **Look for:** a row count above zero, and whether the agent's SQL looks like yours.

# %%
calls = pd.DataFrame(recording_tool.calls)
display(calls)
print("SQL by hand:", hand_sql)
print("Agent used the same SQL:", any(call["sql"] == hand_sql for call in recording_tool.calls))
assert (calls["row_count"] > 0).any(), "No tool call returned rows."
proved.append("I checked the agent's tool calls against my own query")

# %% [markdown]
# ## Step 6. A forged group identity
# **What it does:** builds a request that claims to belong to another group and tries to bind the tool to it.
#
# **Why it matters:** the group is checked before any agent could use the tool. This is an application rule for the workshop,
# not a security boundary.
#
# **Look for:** the line that starts with "Cross-group binding refused".

# %%
from bni_training.data.tool import CrossGroupAccessError, DataRequest

other_group = "group_02" if context.group_id != "group_02" else "group_03"
forged = DataRequest(other_group, "forged", context.dataset_id, context.mission_id)
try:
    context.data_tool().bind(forged)
except CrossGroupAccessError as exc:
    print("Cross-group binding refused:", exc)
    proved.append("A request in another group's name cannot bind the tool")
else:
    raise AssertionError("A cross-group request unexpectedly bound to the tool.")

# %% [markdown]
# ## Hands-on exercise: your turn
# Change `exercise_goal` and run the cell. It builds a **second agent** with your goal, gives it the same task and the same tool,
# and prints both answers so you can compare how the framing changed.
#
# - Easy: ask for a one-sentence answer.
# - Medium: ask for a bulleted answer, or for a formal tone.
# - Hard: ask for the answer to start with the largest value.
#
# **Predict first:** how will the second answer differ? Keep the word "synthetic" in the goal. The agent must still call the tool.
# With the local mock both answers are the same, because the mock always gives one reply; the real model in `cai` mode differs.

# %%
# EXERCISE: edit only this goal. Keep the word "synthetic" and keep using the tool.
exercise_goal = "Explain the result concisely and mention that the data is synthetic."
assert "synthetic" in exercise_goal.lower(), 'Keep the word "synthetic" in the goal.'
calls_before = len(recording_tool.calls)
second_agent = Agent(
    role=analyst_agent.role,
    goal=exercise_goal,
    backstory=analyst_agent.backstory,
    llm=crew_llm,
    tools=[query_group_banking_data],
    verbose=False,
)
second_task = Task(
    description="Answer the participant question: {question}. You must use the data tool.",
    expected_output="A concise answer grounded in the tool rows",
    agent=second_agent,
)
second_output = kickoff_blocking(
    Crew(agents=[second_agent], tasks=[second_task], process=Process.sequential, verbose=False), {"question": question}
)
answers_table = pd.DataFrame({"agent": ["first (original goal)", "second (your goal)"], "answer": [str(crew_output), str(second_output)]})
with pd.option_context("display.max_colwidth", None):  # show each answer in full, not cut with "..."
    display(answers_table)
if len(recording_tool.calls) == calls_before:
    print("The second agent answered without the tool. Strengthen the task wording and run again.")
proved.append("I changed the agent's goal and compared two answers")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes your question, the first agent's answer and the recorded SQL calls as one JSON file in your group's output
# folder. No credential or endpoint is written.

# %%
saved = context.write_output(
    "06_tool_test.json",
    json.dumps({"question": question, "answer": str(crew_output), "tool_calls": recording_tool.calls}, indent=2),
)
print({"saved": saved.name})
proved.append("I saved a credential-free checkpoint")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Eight lines. You asked the data yourself, the agent called the group-bound tool, its SQL is recorded, a forged group identity is refused, and
# two goals gave two answers.
#
# ## Common errors
# If no tool call appears, strengthen the task instruction. If CAI cannot reach vLLM, ask the trainer; never fall back to the local mock in CAI mode.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. How do role, goal, task, tool description and request binding work together?
# 2. How can you tell an answer came from the data and not from the model's imagination?
# 3. Why can the agent not read another group's data, however it is prompted?
#
# ## Reference implementation
# `bni_training.crew` and `bni_training.data.crewai_tool` are reusable references; `scripts/06_crewai_tools.py` is the automation entrypoint.
#
# ## Cleanup
# The next cell stops the explicit local mock (if one was started) and closes the data engine.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
if mock_server:
    mock_server.stop()
context.close()
lab_status("06", LAB_MODE, passed=len(proved), skipped=1 if LAB_MODE == "local" else 0)
