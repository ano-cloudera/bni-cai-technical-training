# %% [markdown]
# # Lab 08: Multi-Agent Workflow
#
# **Audience:** Participant  
# **Estimated duration:** 45–60 minutes
#
# ## Learning objectives
# Define an analyst and reviewer, hand explicit data evidence and analyst output to the reviewer, and validate the final grounded answer.
#
# ## Architecture context
# The analyst retrieves mission data; the reviewer checks clarity and preserves facts. The workflow stays sequential and lightweight for one shared model endpoint.
#
# ## Prerequisites
# Complete Lab 06. CAI mode requires the shared `VLLM_BASE_URL`; local mode uses an explicit deterministic mock.

# %% [markdown]
# ## Configuration validation
# Resolve group context and configure CrewAI against the selected endpoint. Expect mode, group, and mission labels without credentials.

# %%
# Load context and configure the shared-or-explicit-local LLM boundary.
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
mock_server = MockOpenAIServer(reply="The reviewed answer preserves the supplied synthetic facts.").start() if LAB_MODE == "local" else None
base_url = mock_server.base_url if mock_server else os.environ.get("VLLM_BASE_URL", "")
assert base_url, "VLLM_BASE_URL is required in CAI mode."
workflow_llm = crewai_llm(base_url, os.getenv("VLLM_API_KEY", "local-placeholder"))
print({"mode": LAB_MODE, "group_id": context.group_id, "mission": context.bundle.mission_title})

# %% [markdown]
# ## Step-by-step implementation
# Execute the group-bound data tool before agent orchestration. This makes the evidence deterministic and inspectable: participants see the question, SQL, columns, and rows before either agent writes prose. We do not rely on CrewAI's mutable tool recorder because orchestration may copy tool objects.

# %%
# Run the request-bound tool once and keep a bounded evidence package.
question = context.bundle.sample_questions[0]
bound_tool = context.data_tool().bind(context.request())
evidence_sql, evidence_result = bound_tool.query(question)
evidence_rows = [list(row) for row in evidence_result.rows[:25]]
evidence = {
    "question": question,
    "sql": evidence_sql,
    "columns": list(evidence_result.columns),
    "rows": evidence_rows,
    "row_count": evidence_result.row_count,
}
assert evidence_sql.upper().startswith("SELECT") and evidence_rows
print("User question:", question)
print("Generated SQL:", evidence_sql)
print("Returned rows:", evidence_rows)
print({"tool_executed": True, "group_id": context.group_id, "row_count": evidence_result.row_count})

# %% [markdown]
# Define two agents with distinct responsibilities. Neither agent re-runs the tool: both receive the exact validated evidence package, while the reviewer also receives the Analyst task output.

# %%
# Create the analyst and reviewer agents explicitly.
from crewai import Agent, Crew, Process, Task

analyst_agent = Agent(
    role="Synthetic Banking Data Analyst",
    goal="Explain only the supplied SQL and rows supporting the answer",
    backstory="You work only with the current group's synthetic mission data.",
    llm=workflow_llm,
    verbose=False,
)
reviewer_agent = Agent(
    role="Grounding Reviewer",
    goal="Check that the narrative preserves tool facts and adds no unsupported numbers",
    backstory="You improve clarity without changing the analyst's evidence.",
    llm=workflow_llm,
    verbose=False,
)
print({"agents": [analyst_agent.role, reviewer_agent.role]})

# %% [markdown]
# Serialize the same evidence into both task descriptions. `Process.sequential` then passes Analyst output to the Reviewer as additional context. Assertions verify the evidence is not lost before execution.

# %%
# Assemble and execute the two-step sequential workflow.
from bni_training.crew import kickoff_blocking

evidence_text = json.dumps(evidence, default=str)
analyst_task = Task(
    description=f"Analyze this validated group-scoped evidence and draft an answer: {evidence_text}",
    expected_output="SQL, bounded rows, and a factual draft",
    agent=analyst_agent,
)
reviewer_task = Task(
    description=f"Review the draft against this same evidence; add no unsupported number: {evidence_text}",
    expected_output="A concise grounded final answer",
    agent=reviewer_agent,
    context=[analyst_task],
)
assert evidence_sql in analyst_task.description and evidence_sql in reviewer_task.description
workflow = Crew(
    agents=[analyst_agent, reviewer_agent],
    tasks=[analyst_task, reviewer_task],
    process=Process.sequential,
    verbose=False,
)
kickoff_blocking(workflow, {"question": question})
analyst_output = str(analyst_task.output)
reviewer_output = str(reviewer_task.output)
if mock_server:
    request_texts = [json.dumps(item.get("messages", []), default=str) for item in mock_server.requests]
    evidence_request_count = sum(evidence_sql in text for text in request_texts)
    assert evidence_request_count >= 2
print("Analyst output:", analyst_output)
print("Reviewer output:", reviewer_output)

# %% [markdown]
# Apply a deterministic grounding check after the reviewer. Numbers are allowed only when they appeared in tool rows. The mock answer contains no invented numbers, so the default passes.

# %%
# Validate final numerical grounding against actual tool results.
from bni_training.guardrails import validate_grounded_answer

known_numbers = [float(value) for row in evidence_rows for value in row if isinstance(value, (int, float))]
grounded_answer = validate_grounded_answer(reviewer_output, known_numbers)
assert grounded_answer.strip()
print({"grounding": "PASS", "evidence_passed_to_both_agents": True})

# %% [markdown]
# ## Hands-on exercise
# Add or change one reviewer criterion. The default requires a statement that evidence came from the group-scoped tool and remains safe for automated execution.

# %%
# EXERCISE: edit this reviewer criterion and compare the final answer.
exercise_reviewer_criterion = "State that the evidence came from the group-scoped data tool."
assert "group-scoped" in exercise_reviewer_criterion
print({"reviewer_criterion": exercise_reviewer_criterion})

# %% [markdown]
# Save the question, generated SQL, bounded rows, and both agent outputs. This checkpoint makes each explicit hand-off inspectable without storing credentials.

# %%
# Persist the visible workflow hand-off and final result.
summary = {
    "question": question,
    "sql": evidence_sql,
    "rows": evidence_rows,
    "analyst_output": analyst_output,
    "reviewer_output": reviewer_output,
}
saved = context.write_output("08_workflow.json", json.dumps(summary, indent=2))
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# The group-bound tool runs before orchestration; the question, SQL, and returned rows are visible; both agents receive the evidence; and the grounding check passes.
#
# ## Common errors
# If evidence is empty, inspect the group-bound tool before starting the agents. Do not infer execution from a mutable CrewAI recorder. A CAI endpoint error is a FAIL, not permission to start a mock.
#
# ## Completion checkpoint
# Describe what the explicit tool step produced, what the analyst contributed, what the reviewer changed, and how the SQL proves grounding.
#
# ## Reference implementation
# `bni_training.crew` contains reusable workflow utilities; `scripts/08_agent_workflow.py` is the automation reference.
#
# ## Cleanup
# Stop only the explicit local mock and close local data resources.

# %%
# Release local resources and report one executor status line.
from bni_training.workshop.notebook_support import lab_status

if mock_server:
    mock_server.stop()
context.close()
lab_status("08", LAB_MODE, passed=7, skipped=1 if LAB_MODE == "local" else 0)
