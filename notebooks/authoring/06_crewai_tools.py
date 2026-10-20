# %% [markdown]
# # Lab 06: CrewAI Tools
#
# **Audience:** Participant  
# **Estimated duration:** 45–60 minutes
#
# ## Learning objectives
# Define a group-scoped CrewAI tool, configure an agent and task, run a lightweight crew, and inspect recorded tool calls.
#
# ## Architecture context
# An agent is an LLM with instructions and tools. The data tool is bound to one validated group request, so an agent cannot select another group's dataset.
#
# ## Prerequisites
# Complete Labs 03–05. CAI mode needs the shared `VLLM_BASE_URL`; local mode announces an explicit mock.

# %% [markdown]
# ## Configuration validation
# Resolve group context and configure CrewAI against either the shared endpoint or explicit local mock. Expect mode and group labels, never credentials.

# %%
# Load workshop context and configure the LLM boundary.
import json
import os
import sys
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
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
group_env = Path.cwd().parent / "config" / "group.env"
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
print({"mode": LAB_MODE, "group_id": context.group_id, "mission_id": context.mission_id})

# %% [markdown]
# ## Step-by-step implementation
# Bind the data tool to the current request and wrap it with CrewAI's `@tool`. The wrapper returns visible SQL, columns, rows, and row count. Expect a named tool with no way to accept a group id.

# %%
# Define a visible, request-bound CrewAI tool and record its calls.
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

print({"tool": query_group_banking_data.name, "bound_group": context.group_id})

# %% [markdown]
# Define the banking analyst explicitly. Role, goal, backstory, LLM, and tools are visible so participants can see what changes agent behavior. Expect one agent with exactly one group-scoped tool.

# %%
# Create the agent whose only data access is the bound workshop tool.
from crewai import Agent, Crew, Process, Task

analyst_agent = Agent(
    role="Synthetic Banking Analyst",
    goal="Use the approved tool for grounded mission facts",
    backstory="You analyze only the synthetic dataset assigned to this workshop group.",
    llm=crew_llm,
    tools=[query_group_banking_data],
    verbose=False,
)
print({"role": analyst_agent.role, "tools": [item.name for item in analyst_agent.tools]})

# %% [markdown]
# Create a task and sequential crew, then use `kickoff_blocking` because Jupyter already runs an event loop. The task requires tool use; expect a final answer and at least one recorded SQL call.

# %%
# Run one small CrewAI task and inspect its actual tool activity.
from bni_training.crew import kickoff_blocking

question = context.bundle.sample_questions[0]
analysis_task = Task(
    description="Answer the participant question: {question}. You must use the data tool.",
    expected_output="A concise answer grounded in the tool rows",
    agent=analyst_agent,
)
crew = Crew(agents=[analyst_agent], tasks=[analysis_task], process=Process.sequential, verbose=False)
crew_output = kickoff_blocking(crew, {"question": question})
assert recording_tool.calls, "The agent did not call the data tool; inspect its goal and task."
print({"question": question, "tool_calls": recording_tool.calls, "answer": str(crew_output)})

# %% [markdown]
# A forged request is rejected before an agent could use it. This demonstrates operational group separation at the application layer. Expect a friendly cross-group refusal.

# %%
# Prove the underlying tool refuses a request carrying another group identity.
from bni_training.data.tool import CrossGroupAccessError, DataRequest

other_group = "group_02" if context.group_id != "group_02" else "group_03"
forged = DataRequest(other_group, "forged", context.dataset_id, context.mission_id)
try:
    context.data_tool().bind(forged)
except CrossGroupAccessError as exc:
    print("Cross-group binding refused:", exc)
else:
    raise AssertionError("A cross-group request unexpectedly bound to the tool.")

# %% [markdown]
# ## Hands-on exercise
# Change only the goal sentence below, then compare how the agent frames the same mission question. The runnable default keeps tool use mandatory.

# %%
# EXERCISE: edit this safe instruction while preserving tool grounding.
exercise_goal = "Explain the result concisely and mention that the data is synthetic."
assert "synthetic" in exercise_goal.lower()
print({"exercise_goal": exercise_goal, "recorded_calls": len(recording_tool.calls)})

# %% [markdown]
# Save the question, final answer, and recorded SQL. No credential or endpoint is written.

# %%
# Persist a credential-free agent checkpoint.
saved = context.write_output(
    "06_tool_test.json",
    json.dumps({"question": question, "answer": str(crew_output), "tool_calls": recording_tool.calls}, indent=2),
)
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# The crew calls the group-bound tool at least once, returns an answer, records SQL, and refuses a forged group identity.
#
# ## Common errors
# If no tool call appears, strengthen the task instruction. If CAI cannot reach vLLM, ask the trainer; never fall back to the local mock in CAI mode.
#
# ## Completion checkpoint
# Explain how role, goal, task, tool description, and request binding work together.
#
# ## Reference implementation
# `bni_training.crew` and `bni_training.data.crewai_tool` are reusable references; `scripts/06_crewai_tools.py` is the automation entrypoint.
#
# ## Cleanup
# Stop only the explicit local mock and close the local CSV engine.

# %%
# Release local resources and print one executor status line.
from bni_training.workshop.notebook_support import lab_status

if mock_server:
    mock_server.stop()
context.close()
lab_status("06", LAB_MODE, passed=6, skipped=1 if LAB_MODE == "local" else 0)
