# %% [markdown]
# # Lab 04: CSV Data Access
#
# **Audience:** Participant  
# **Estimated duration:** 35–45 minutes
#
# ## Learning objectives
# Inspect the assigned logical bundle, run guarded read-only SQL, understand row limits, and observe table, write, and cross-group refusals.
#
# ## Architecture context
# One synthetic dataset in `data/raw` serves ten logical bundles. CSV is the participant default; Impala is an optional trainer extension and is never an automatic fallback.
#
# ## Prerequisites
# Complete Lab 00 and load the generated group context. This notebook writes only a safe preview into the assigned output folder.

# %% [markdown]
# ## Configuration validation
# Resolve the group context and create its guarded data tool. Expect the assigned dataset, mission, tables, and exposed columns.

# %%
# Load the validated group context and its read-only CSV data tool.
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
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
tool = context.data_tool()
request = context.request()
description = tool.describe()
print({"dataset_id": context.dataset_id, "mission_id": context.mission_id, "tables": list(description["tables"])})

# %% [markdown]
# ## Step-by-step implementation
# Run visible `SELECT` statements with the request identity. The data tool enforces the bundle, read-only SQL, and a 200-row maximum. Expect positive counts and at most three preview rows per table.

# %%
# Execute hand-written read-only SQL against each allowed logical table.
preview = {}
for table in context.bundle.tables:
    count_result = tool.run_sql(f"SELECT COUNT(*) AS row_count FROM {table}", request)
    sample_result = tool.run_sql(f"SELECT * FROM {table} LIMIT 3", request)
    preview[table] = {
        "row_count": count_result.rows[0][0],
        "columns": list(sample_result.columns),
        "sample": sample_result.rows,
    }
    print({"table": table, "rows": count_result.rows[0][0], "columns": list(sample_result.columns)})

# %% [markdown]
# Try an unassigned table and a destructive statement. `RestrictedTableError` and the SQL validator turn both into friendly refusals. Expect two refusal messages and no data changes.

# %%
# Demonstrate table and write guardrails without bypassing them.
from bni_training.data.engine import RestrictedTableError

all_tables = {"branches", "customers", "accounts", "transactions", "loans"}
outside_table = next(iter(sorted(all_tables - set(context.bundle.tables))), None)
if outside_table:
    try:
        tool.run_sql(f"SELECT * FROM {outside_table} LIMIT 1", request)
    except RestrictedTableError as exc:
        print("Unassigned table refused:", exc)
try:
    tool.run_sql("DELETE FROM customers", request)
except ValueError as exc:
    print("Write refused:", exc)

# %% [markdown]
# Bind a deliberately different group identity to the same tool. Application-layer validation must reject it before SQL runs. Expect a cross-group refusal sentence.

# %%
# Prove that request identity cannot switch the bundle to another group.
from bni_training.data.tool import CrossGroupAccessError, DataRequest

other_group = "group_02" if context.group_id != "group_02" else "group_03"
cross_group_request = DataRequest(other_group, "exercise", context.dataset_id, context.mission_id)
try:
    tool.run_sql(f"SELECT COUNT(*) FROM {context.bundle.tables[0]}", cross_group_request)
except CrossGroupAccessError as exc:
    print("Cross-group request refused:", exc)
else:
    raise AssertionError("A cross-group request unexpectedly ran.")

# %% [markdown]
# ## Hands-on exercise
# Change `exercise_sql` to one additional read-only analytical question using only assigned tables. The default count query is valid for every group.

# %%
# EXERCISE: edit only this SELECT while keeping the assigned table and row limit.
exercise_sql = f"SELECT COUNT(*) AS row_count FROM {context.bundle.tables[0]}"
exercise_result = tool.run_sql(exercise_sql, request)
assert exercise_result.rows and exercise_result.rows[0][0] > 0
print({"exercise_sql": exercise_sql, "result": exercise_result.rows})

# %% [markdown]
# Save the bounded preview as JSON. This writes only under the current group output folder and never copies the physical CSV dataset.

# %%
# Persist a safe preview for later comparison.
saved = context.write_output("04_dataset_preview.json", json.dumps(preview, indent=2, default=str))
print({"saved": saved.name, "tables": list(preview)})

# %% [markdown]
# ## Expected result
# Assigned table counts and schemas appear, unassigned/write/cross-group attempts are refused, and one preview JSON file is saved.
#
# ## Common errors
# A refused column or table is outside the mission bundle. A refused write is expected. Do not switch to Impala or another group to bypass a refusal.
#
# ## Completion checkpoint
# Explain the difference between one physical dataset, a logical bundle, and operational group separation.
#
# ## Reference implementation
# The guarded engine and tool live in `bni_training.data`; `scripts/04_csv_data_access.py` is the automation reference.
#
# ## Cleanup
# Close the in-memory CSV engine. Keep the preview checkpoint; no shared service was started.

# %%
# Close the data engine and report notebook completion.
from bni_training.workshop.notebook_support import lab_status

context.close()
lab_status("04", LAB_MODE, passed=6)
