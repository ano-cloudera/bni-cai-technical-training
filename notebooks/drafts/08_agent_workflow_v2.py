# %% [markdown]
# # Lab 08: Multi-Agent Workflow (draft v2)
#
# **Audience:** Participant
# **Estimated duration:** 45–60 minutes
#
# ## What you will learn
# By the end you can: explain why evidence is collected before any agent writes, hand the same evidence to an analyst and a
# reviewer, check that every number in the final answer comes from the data, see a made-up number rejected, and change what the
# reviewer looks for.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It opens your group's data tool and connects the model. You do not edit it.
# 2. **Nine steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Your turn.** You change the reviewer's criterion and compare answers.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. Complete Lab 06 first. In `cai` mode the two agents call the real model, so Step 4 can take
# up to a minute.
#
# ## Architecture context
# In Lab 06 one agent chose to call a tool. Here the data is fetched **first**, by plain code, so you can see the question, the SQL and
# the rows before any agent writes a word. Then an **analyst** drafts an answer from that evidence and a **reviewer** checks the draft
# against the same evidence. A final rule rejects any number that is not in the data.

# %% [markdown]
# ## Setup
# This cell finds the repository, reads your group's settings, opens the data tool and connects CrewAI to the model. You do not
# need to change anything. It prints your group, the mission and the mode, never a credential.

# %%
# Setup: find the repository, load your group's settings and connect the model. Nothing to edit.
import json
import os
import re
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
mock_server = MockOpenAIServer(reply="The reviewed answer preserves the supplied synthetic facts.").start() if LAB_MODE == "local" else None
base_url = mock_server.base_url if mock_server else os.environ.get("VLLM_BASE_URL", "")
assert base_url, "VLLM_BASE_URL is required in CAI mode."
workflow_llm = crewai_llm(base_url, os.getenv("VLLM_API_KEY", "local-placeholder"))
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id, "mission": context.bundle.mission_title})

# %% [markdown]
# ## Step 1. Collect the evidence first
# **What it does:** runs the group-bound data tool once with the sample question of your mission, and shows the SQL and the rows.
#
# **Why it matters:** agents write fluent text, but fluent is not true. By fetching the data first with plain code, the evidence is
# fixed and visible before any agent speaks. Both agents will receive exactly this evidence.
#
# **Predict first:** what will the rows contain?

# %%
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
print("Question:", question)
print("SQL:", evidence_sql)
display(pd.DataFrame(evidence_rows, columns=evidence["columns"]))
proved.append("I collected the evidence (question, SQL and rows) before any agent")

# %% [markdown]
# ## Step 2. Two agents, two jobs
# **What it does:** creates an **analyst**, who explains the evidence, and a **reviewer**, who checks the draft. Neither agent has a
# tool: both only receive the evidence as text.
#
# **Why it matters:** splitting the work gives you a second pair of eyes. Different goals make the agents behave differently.
#
# **Look for:** the two roles and their goals in the table.

# %%
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
display(pd.DataFrame({"role": [analyst_agent.role, reviewer_agent.role], "goal": [analyst_agent.goal, reviewer_agent.goal]}))
proved.append("I defined an analyst and a reviewer with different goals")

# %% [markdown]
# ## Step 3. Give both the same evidence
# **What it does:** writes two tasks. Both contain the evidence as text. The reviewer task also receives the analyst's output
# (`context=[analyst_task]`), and `Process.sequential` runs the analyst first.
#
# **Why it matters:** the reviewer checks the draft against the **same** facts, not against the analyst's memory. The assertion
# proves the SQL really is inside both task descriptions.
#
# **Look for:** `True` for both tasks.

# %%
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
print("Evidence is in the analyst task:", evidence_sql in analyst_task.description)
print("Evidence is in the reviewer task:", evidence_sql in reviewer_task.description)
assert evidence_sql in analyst_task.description and evidence_sql in reviewer_task.description
proved.append("I gave the same evidence to both tasks")

# %% [markdown]
# ## Step 4. Run the workflow
# **What it does:** runs the analyst, then the reviewer, and puts both outputs side by side.
#
# **Why it matters:** this is the multi-agent idea: one agent's output becomes the next agent's input. In `cai` mode this calls the
# real model twice.
#
# **Predict first:** how will the reviewer's text differ from the analyst's?

# %%
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
    assert sum(evidence_sql in text for text in request_texts) >= 2, "Both agents must receive the evidence."
display(pd.DataFrame({"agent": ["analyst (draft)", "reviewer (final)"], "output": [analyst_output, reviewer_output]}))
proved.append("I ran the analyst and the reviewer in sequence")

# %% [markdown]
# ## Step 5. Which numbers does the final answer contain?
# **What it does:** finds every number in the reviewer's answer and checks whether it also appears in the evidence rows.
#
# **Why it matters:** this is the check a human reader cannot do by eye. A number that is not in the data is a number the model made up.
#
# **Look for:** the column `in the evidence?`. Every row should say `True`. With the local mock the answer has no number, so the table is empty.

# %%
known_numbers = [float(value) for row in evidence_rows for value in row if isinstance(value, (int, float))]
allowed = {round(value, 4) for value in known_numbers}
mentioned = [float(text.replace(",", "")) for text in re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", reviewer_output)]
if mentioned:
    display(pd.DataFrame({"number in the answer": mentioned, "in the evidence?": [round(value, 4) in allowed for value in mentioned]}))
else:
    print("The answer contains no number, so there is nothing to check.")
proved.append("I listed the numbers in the final answer and compared them with the evidence")

# %% [markdown]
# ## Step 6. The grounding rule
# **What it does:** applies `validate_grounded_answer`, the same rule as Lab 11. It accepts an answer only when every number in it
# is among the numbers from the tool rows.
#
# **Why it matters:** a rule in code does not get tired and does not trust the model. It is the last gate before an answer is shown.
#
# **Look for:** `grounding: PASS`.

# %%
from bni_training.guardrails import GuardrailError, validate_grounded_answer

grounded_answer = validate_grounded_answer(reviewer_output, known_numbers)
assert grounded_answer.strip()
print({"grounding": "PASS"})
proved.append("The final answer passed the grounding rule")

# %% [markdown]
# ## Step 7. A made-up number is rejected
# **What it does:** feeds the rule an answer with a number that is **not** in your data.
#
# **Why it matters:** a rule is only trustworthy if you have seen it say no. This is the case the rule exists for.
#
# **Look for:** the line that starts with "Rejected".

# %%
invented = "The verified total is 987654321.12."
try:
    validate_grounded_answer(invented, known_numbers)
except GuardrailError as exc:
    print("Rejected:", exc)
    proved.append("A made-up number was rejected by the rule")
else:
    raise AssertionError("An invented number unexpectedly passed.")

# %% [markdown]
# ## Your turn
# Change `exercise_reviewer_criterion` and run the cell. It builds a **new reviewer** with your criterion, gives it the analyst's draft
# and the same evidence, and applies the grounding rule to its answer.
#
# - Easy: ask the reviewer to answer in one sentence.
# - Medium: ask it to list the highest value first.
# - Hard: ask it to add a percentage, then see what the rule says about a number that is not in the rows.
#
# **Predict first:** will the rule accept the new answer? Keep the words "group-scoped" in the criterion. If the rule blocks the answer,
# that is the rule doing its job: read why and adjust the criterion.

# %%
# EXERCISE: edit this reviewer criterion and compare the final answer.
exercise_reviewer_criterion = "State that the evidence came from the group-scoped data tool."
assert "group-scoped" in exercise_reviewer_criterion, 'Keep the words "group-scoped" in the criterion.'
custom_reviewer = Agent(
    role="Grounding Reviewer",
    goal=f"Check the narrative against the evidence and add no unsupported numbers. Also: {exercise_reviewer_criterion}",
    backstory="You improve clarity without changing the analyst's evidence.",
    llm=workflow_llm,
    verbose=False,
)
custom_task = Task(
    description=f"Analyst draft: {analyst_output}\nReview it against this evidence: {evidence_text}",
    expected_output="A concise grounded final answer",
    agent=custom_reviewer,
)
custom_output = str(
    kickoff_blocking(
        Crew(agents=[custom_reviewer], tasks=[custom_task], process=Process.sequential, verbose=False), {"question": question}
    )
)
display(pd.DataFrame({"reviewer": ["original", "with your criterion"], "answer": [reviewer_output, custom_output]}))
try:
    validate_grounded_answer(custom_output, known_numbers)
    print("Grounding rule: PASS")
except GuardrailError as exc:
    print("Grounding rule blocked this answer:", exc)
proved.append("I changed the reviewer's criterion and compared the answers")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes the question, the SQL, the rows and both agent outputs to your group's output folder.
#
# **Why it matters:** each hand-off stays inspectable later, and the file holds no credential.

# %%
summary = {
    "question": question,
    "sql": evidence_sql,
    "rows": evidence_rows,
    "analyst_output": analyst_output,
    "reviewer_output": reviewer_output,
}
saved = context.write_output("08_workflow.json", json.dumps(summary, indent=2))
print({"saved": saved.name})
proved.append("I saved the workflow checkpoint")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Nine lines. The evidence was fetched first, both agents received it, the final answer passed the grounding rule, a made-up number was
# rejected, and one checkpoint file is saved.
#
# ## Common errors
# If the evidence is empty, check the group-bound data tool before starting the agents. A model endpoint error is a failure, not permission
# to start a mock. If the rule blocks the final answer, the model wrote a number that is not in the rows: run the step again or tighten the
# reviewer's criterion.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. Why is the evidence collected before the agents run?
# 2. What did the analyst add, and what did the reviewer change?
# 3. How does the SQL, together with the grounding rule, prove the answer is grounded?
#
# ## Reference implementation
# `bni_training.crew` contains reusable workflow utilities; `scripts/08_agent_workflow.py` is the automation reference.
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
lab_status("08", LAB_MODE, passed=len(proved), skipped=1 if LAB_MODE == "local" else 0)
