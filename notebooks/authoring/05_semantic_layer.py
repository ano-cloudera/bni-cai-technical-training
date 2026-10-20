# %% [markdown]
# # Lab 05: Semantic Layer
#
# **Audience:** Participant  
# **Estimated duration:** 30–40 minutes
#
# ## Learning objectives
# Inspect metrics and relationships, plan SQL from business language, execute the plan, and observe mission-scoped metric validation.
#
# ## Architecture context
# The semantic layer maps banking terms to deterministic read-only SQL. Joins move toward parent tables to avoid double counting, and every plan stays inside the group's bundle.
#
# ## Prerequisites
# Complete Lab 04 and use the same validated group context and CSV backend.

# %% [markdown]
# ## Configuration validation
# Load the group bundle, guarded data tool, and semantic model. Expect the mission's metric names and a non-empty relationship graph.

# %%
# Resolve group context and load the explicit semantic model.
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
from bni_training.workshop.notebook_support import load_group_env

# A generated workspace provides config/group.env (LAB_MODE, GROUP_ID, GROUP_WORKSPACE, VLLM_BASE_URL, VLLM_MODEL).
# Values already set in the Session environment win. No manual setup is needed.
load_group_env(Path.cwd().parent / "config" / "group.env")
LAB_MODE = os.getenv("LAB_MODE", "local").lower()
group_env = Path.cwd().parent / "config" / "group.env"
if group_env.is_file() and not os.getenv("GROUP_ENV_FILE"):
    os.environ["GROUP_ENV_FILE"] = str(group_env)
from bni_training.data.semantic_layer import SemanticError, SemanticModel
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
semantic = SemanticModel.load()
tool = context.data_tool()
bundle = context.bundle
print({"metrics": list(bundle.allowed_metrics), "tables": list(bundle.tables), "terms": len(semantic.terms)})

# %% [markdown]
# ## Step-by-step implementation
# Plan the first allowed metric directly. `allowed_tables` and `allowed_metrics` are explicit validation boundaries, while `limit` caps output. Expect readable SQL ending in a bounded limit.

# %%
# Build a visible semantic plan with the mission's first allowed metric.
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

# %% [markdown]
# Execute the planned SQL through the guarded data tool. This preserves the same bundle and row policies as Lab 04. Expect at least one result row.

# %%
# Run the planned read-only SQL and inspect its bounded result.
planned_result = tool.run_sql(planned.sql, context.request())
assert planned_result.row_count > 0
print({"columns": list(planned_result.columns), "rows": planned_result.rows[:5]})

# %% [markdown]
# Resolve a mission sample question to show how synonyms and dimensions become SQL. Expect the question, chosen metric, breakdowns, and SQL to remain visible.

# %%
# Translate one business question through the semantic layer.
sample_question = bundle.sample_questions[0]
question_plan = semantic.resolve_question(
    sample_question,
    allowed_tables=bundle.tables,
    allowed_metrics=bundle.allowed_metrics,
)
question_result = tool.run_sql(question_plan.sql, context.request())
print({"question": sample_question, "metric": question_plan.metric, "dimensions": question_plan.dimensions})
print("Question SQL:", question_plan.sql)
assert question_result.row_count > 0

# %% [markdown]
# Request a metric outside the mission. The semantic validator should refuse it before SQL execution. Expect a friendly scope message when such a metric exists.

# %%
# Demonstrate mission-level metric validation.
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
    else:
        raise AssertionError("An out-of-mission metric unexpectedly planned.")

# %% [markdown]
# ## Hands-on exercise
# Change `exercise_question` to another listed sample or a safe metric question. The default uses the mission's first sample and must return rows.

# %%
# EXERCISE: edit only the business question; group and metric scope stay fixed.
exercise_question = bundle.sample_questions[0]
exercise_sql, exercise_result = tool.query(exercise_question, context.request())
assert exercise_result.row_count > 0, "Try a mission question containing one allowed metric."
print({"exercise_question": exercise_question, "sql": exercise_sql, "rows": exercise_result.row_count})

# %% [markdown]
# Save the semantic checkpoint without modifying tracked metric files. A custom production metric would require review; participant experiments stay in their output workspace.

# %%
# Persist only the visible plan and row count for the checkpoint.
summary = {
    "group_id": context.group_id,
    "question": exercise_question,
    "sql": exercise_sql,
    "row_count": exercise_result.row_count,
}
saved = context.write_output("05_semantic_summary.json", json.dumps(summary, indent=2))
print({"saved": saved.name})

# %% [markdown]
# ## Expected result
# Metrics are visible, direct and question-based plans print SQL, results are bounded, and an out-of-mission metric is refused.
#
# ## Common errors
# An unknown metric or breakdown produces a teaching message. Use the mission's available metrics and no more than two dimensions.
#
# ## Completion checkpoint
# Explain how metrics, dimensions, parent joins, and bundle restrictions shape the planned SQL.
#
# ## Reference implementation
# `bni_training.data.semantic_layer` is reusable production code; `scripts/05_semantic_layer.py` is the automation reference.
#
# ## Cleanup
# Close the in-memory data engine. Keep the semantic summary in the assigned output folder.

# %%
# Close resources and print one executor status line.
from bni_training.workshop.notebook_support import lab_status

context.close()
lab_status("05", LAB_MODE, passed=6)
