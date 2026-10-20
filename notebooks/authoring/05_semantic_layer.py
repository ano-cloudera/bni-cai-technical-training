# %% [markdown]
# # Lab 05: Semantic Layer
#
# **Audience:** Participant
# **Estimated duration:** 30–40 minutes
#
# ## Learning objectives
# By the end you can: explain what a metric and a dimension are, see the SQL a business question turns into, check that a
# metric outside your mission is refused, and ask the semantic layer a question of your own.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It opens your group's data tool and the semantic model. You do not edit it.
# 2. **Eight steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Your turn.** You choose one business question.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. They are safe to run again. Complete Lab 04 first.
#
# ## Prerequisites
# Complete Lab 04. It uses the same group context and the same CSV data.
#
# ## Architecture context
# In Lab 04 you wrote SQL by hand. A **semantic layer** is a small dictionary of business words (metrics such as "total
# outstanding", and dimensions such as "risk band") that it turns into safe, read-only SQL for you. Joins move toward
# parent tables to avoid double counting, and every plan stays inside your group's tables and metrics.

# %% [markdown]
# ## Configuration validation (setup)
# This cell finds the repository, reads your group's settings (`config/group.env`), and opens the data tool and the
# semantic model. You do not need to change anything. It ends by printing your group and the mode.

# %%
# Setup: find the repository, load your group's settings, open the guarded data tool and the semantic model. Nothing to edit.
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
from bni_training.data.semantic_layer import SemanticError, SemanticModel
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
semantic = SemanticModel.load()
tool = context.data_tool()
bundle = context.bundle
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id})

# %% [markdown]
# ## Step-by-step implementation
# Each step says what the cell does, why it matters and what to look for.
#
# ## Step 1. What can I ask for?
# **What it does:** lists the metrics and the tables your mission allows, and how many business terms the semantic model knows.
#
# **Why it matters:** a metric is a named calculation ("total outstanding"). You ask for the name, and the layer writes the SQL.
# Your mission allows only some metrics and tables. Other groups have other lists.
#
# **Predict first:** which metric would you ask for to find how much money is still owed?

# %%
print("Mission:", bundle.mission_title)
display(pd.DataFrame({"metric you may ask for": list(bundle.allowed_metrics)}))
print("Your tables:", ", ".join(bundle.tables))
print("Business terms known to the semantic model:", len(semantic.terms))
assert bundle.allowed_metrics, "Your mission has no metric; ask the trainer."
proved.append(f"I know my mission's metrics: {', '.join(bundle.allowed_metrics)}")

# %% [markdown]
# ## Step 2. From a metric name to SQL
# **What it does:** asks the semantic layer to plan your first allowed metric. It prints the tables it will use and the SQL.
# `limit=25` caps the number of rows.
#
# **Why it matters:** this is the heart of the lab. You gave a business name and got a complete, readable `SELECT` that
# stays inside your tables and ends with a limit.
#
# **Look for:** `FROM`, any `GROUP BY`, and `LIMIT 25` at the end.

# %%
metric_name = bundle.allowed_metrics[0]
planned = semantic.plan(
    metric_name,
    allowed_tables=bundle.tables,
    allowed_metrics=bundle.allowed_metrics,
    limit=25,
)
print({"metric": planned.metric, "tables": sorted(planned.tables)})
print("Planned SQL:", planned.sql)
assert "SELECT" in planned.sql and "LIMIT 25" in planned.sql
proved.append(f"I planned the metric '{metric_name}' into SQL with a row limit")

# %% [markdown]
# ## Step 3. Run the plan
# **What it does:** sends the planned SQL through the same guarded data tool you used in Lab 04, then shows the result as a table.
#
# **Why it matters:** planning does not touch any data. Running does, and the tool still enforces your tables, read-only SQL
# and the row cap.
#
# **Predict first:** how many rows do you expect? Then compare.

# %%
planned_result = tool.run_sql(planned.sql, context.request())
display(pd.DataFrame(planned_result.rows, columns=planned_result.columns))
print("Rows returned:", planned_result.row_count)
assert planned_result.row_count > 0
assert planned_result.row_count <= 25, "The plan's limit of 25 was not applied."
proved.append("I ran a planned query and the limit kept it small")

# %% [markdown]
# ## Step 4. A business question
# **What it does:** takes the first sample question of your mission, written in plain English, and resolves it into a metric,
# a breakdown (a **dimension**, such as "by risk band") and SQL.
#
# **Why it matters:** this is how a non-technical user can ask in their own words. Synonyms ("outstanding", "exposure") map to
# one metric, and "by ..." maps to a dimension.
#
# **Look for:** the metric and the dimension printed in the first line, and the SQL below it.

# %%
sample_question = bundle.sample_questions[0]
question_plan = semantic.resolve_question(
    sample_question,
    allowed_tables=bundle.tables,
    allowed_metrics=bundle.allowed_metrics,
)
question_result = tool.run_sql(question_plan.sql, context.request())
print({"question": sample_question, "metric": question_plan.metric, "dimensions": question_plan.dimensions})
print("Question SQL:", question_plan.sql)
display(pd.DataFrame(question_result.rows, columns=question_result.columns))
assert question_result.row_count > 0
proved.append("I turned a business question into a metric, a dimension and SQL")

# %% [markdown]
# ## Step 5. Two ways to the same answer
# **What it does:** asks the data tool for the same question in one call (`tool.query`) and prints its SQL next to the plan from
# Step 4.
#
# **Why it matters:** `tool.query` is the shortcut the Portal uses. Seeing both side by side shows that the Portal and your
# notebook follow the same rules. Lab 12 compares them for you.
#
# **Look for:** whether the two SQL texts look the same.

# %%
shortcut_sql, shortcut_result = tool.query(sample_question, context.request())
print("Plan SQL:     ", question_plan.sql)
print("tool.query SQL:", shortcut_sql)
print("Same rows:", shortcut_result.row_count == question_result.row_count)
proved.append("I saw that the one-call shortcut and my own plan use the same rules")

# %% [markdown]
# ## Step 6. A metric that is not in my mission
# **What it does:** picks a metric that exists in the semantic model but not in your mission and asks for it.
#
# **Why it matters:** the check happens in the planner, before any SQL runs. The refusal is a friendly message, not a crash.
#
# **Look for:** the line that starts with "Out-of-mission metric refused".

# %%
outside_metric = next((name for name in semantic.metrics if name not in bundle.allowed_metrics), None)
if outside_metric:
    try:
        semantic.plan(
            outside_metric,
            allowed_tables=bundle.tables,
            allowed_metrics=bundle.allowed_metrics,
        )
    except SemanticError as exc:
        print("Out-of-mission metric refused:", exc)
        proved.append(f"A metric outside my mission ({outside_metric}) is refused")
    else:
        raise AssertionError("An out-of-mission metric unexpectedly planned.")
else:
    print("Your mission allows every metric, so there is nothing to refuse here.")

# %% [markdown]
# ## Step 7. Which questions can I try?
# **What it does:** lists the sample questions of your mission.
#
# **Why it matters:** the semantic layer understands a limited vocabulary. These questions are known to work, so they are a safe
# place to start your own.

# %%
display(pd.DataFrame({"sample question": list(bundle.sample_questions)}))
proved.append("I know which sample questions my mission offers")

# %% [markdown]
# ## Hands-on exercise: your turn
# Choose a business question from Step 7 (or change a word, for example the dimension) and set `exercise_question`.
#
# - Easy: pick another sample question.
# - Medium: change the dimension, for example "by segment" instead of "by risk band", if your mission lists it.
# - Hard: predict the number of result rows before you run the cell, then check.
#
# **Predict first:** what will the table look like? The default is the first sample question, so the cell passes until you
# change it. If your question is not understood you get a teaching message: use words from Step 1 and Step 7.

# %%
# EXERCISE: edit only the business question; group and metric scope stay fixed.
exercise_question = bundle.sample_questions[0]
exercise_sql, exercise_result = tool.query(exercise_question, context.request())
assert exercise_result.row_count > 0, "Try a mission question containing one allowed metric."
print(exercise_question)
print("SQL:", exercise_sql)
display(pd.DataFrame(exercise_result.rows, columns=exercise_result.columns).head(10))
proved.append("I asked the semantic layer a question of my own")

# %% [markdown]
# ## Save your checkpoint
# **What it does:** writes your question, its SQL and the row count as one JSON file in your group's output folder.
#
# **Why it matters:** results stay in your own folder, and no tracked metric file is changed. A new production metric would
# need review; your experiments stay in your workspace.

# %%
summary = {
    "group_id": context.group_id,
    "question": exercise_question,
    "sql": exercise_sql,
    "row_count": exercise_result.row_count,
}
saved = context.write_output("05_semantic_summary.json", json.dumps(summary, indent=2))
print({"saved": saved.name})
proved.append("I saved a checkpoint in my group's output folder")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and run it.
#
# ## Expected result
# Nine to ten lines. Your metrics are visible, plans print readable SQL, results are small tables, a metric outside your mission
# is refused, and one checkpoint file is saved.
#
# ## Common errors
# An unknown metric or breakdown produces a teaching message. Use the metrics of Step 1 and no more than two dimensions.
#
# ## Completion checkpoint
# Explain in your own words:
# 1. What is the difference between a metric and a dimension?
# 2. Why does the plan stay inside your tables and end with a limit?
# 3. Why is it useful that the Portal and your notebook use the same rules?
#
# ## Reference implementation
# `bni_training.data.semantic_layer` is reusable production code; `scripts/05_semantic_layer.py` is the automation reference.
#
# ## Cleanup
# The next cell closes the in-memory data engine. Keep the checkpoint file.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
context.close()
lab_status("05", LAB_MODE, passed=len(proved))
