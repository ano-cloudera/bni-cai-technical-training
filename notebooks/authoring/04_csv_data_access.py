# %% [markdown]
# # Lab 04: CSV Data Access
#
# **Audience:** Participant
# **Estimated duration:** 35–45 minutes
#
# ## What you will learn
# By the end you can: look at the tables your mission gives you, ask them questions with SQL, see why some requests
# are refused, and write one question of your own.
#
# ## How this notebook is organised
# 1. **Setup (one cell).** It finds your group and opens the data tool. You do not edit it.
# 2. **Ten steps.** Each step says what the next cell does and why, you run it, and you read what it prints.
# 3. **Your turn.** You write one SQL question yourself.
# 4. **Closing.** A list of what you proved, and the questions to explain back to your trainer.
#
# Run the cells from top to bottom. They are safe to run again.
#
# ## Architecture context
# One synthetic dataset serves ten groups. Your group sees only the tables of its mission. The data tool, not
# the notebook, enforces that: it only allows read-only `SELECT`, only your tables, and at most 200 rows.

# %% [markdown]
# ## Setup
# This cell finds the repository, reads your group's settings (`config/group.env`), and opens the read-only data tool.
# You do not need to change anything. It ends by printing your group and the mode (`cai` means the real shared services).

# %%
# Setup: find the repository, load your group's settings and open the guarded data tool. Nothing to edit.
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
from bni_training.workshop.lab_context import resolve_lab_context

context = resolve_lab_context(LAB_MODE)
tool = context.data_tool()
request = context.request()
proved = []  # one sentence per thing you prove; printed in the closing
print({"mode": LAB_MODE, "group_id": context.group_id})

# %% [markdown]
# ## Step 1. What is my assignment?
# **What it does:** prints your group, your mission, your dataset and the tables you may use.
#
# **Why it matters:** every later step uses only these tables. Other groups have a different mission and different tables.
#
# **Predict first:** which tables do you expect? Then run the cell and compare.

# %%
print("Group:       ", context.group_id)
print("Mission:     ", context.bundle.mission_title)
print("Dataset:     ", context.dataset_id)
print("Your tables: ", ", ".join(context.bundle.tables))
proved.append(f"I know my assignment: {context.group_id}, tables {', '.join(context.bundle.tables)}")

# %% [markdown]
# ## Step 2. What do the tables look like?
# **What it does:** for each of your tables it runs `SELECT * FROM <table> LIMIT 3` through the data tool, then prints the
# column names and three rows.
#
# **Why it matters:** you can only write good SQL when you know the column names. `LIMIT 3` keeps the answer small.
#
# **New here:** `pd.DataFrame(rows, columns=columns)` turns rows into a table you can read. It is the only pandas you need
# in this lab.
#
# **Look for:** one column that looks like a category (a status, a band, a type). You use it in Step 4.

# %%
structure = {}
for table in context.bundle.tables:
    sample = tool.run_sql(f"SELECT * FROM {table} LIMIT 3", request)
    structure[table] = {"columns": list(sample.columns), "sample": sample.rows}
    print(f"{table}: {len(sample.columns)} columns")
    display(pd.DataFrame(sample.rows, columns=sample.columns))
proved.append("I can list the columns and look at sample rows of every table I may use")

# %% [markdown]
# ## Step 3. How big are the tables?
# **What it does:** counts the rows of each table with `SELECT COUNT(*)`.
#
# **Why it matters:** `COUNT(*)` is the first question to ask of any table. It also proves the data is really there.
#
# **Predict first:** which of your tables has the most rows?

# %%
counts = {}
for table in context.bundle.tables:
    result = tool.run_sql(f"SELECT COUNT(*) AS row_count FROM {table}", request)
    counts[table] = result.rows[0][0]
display(pd.DataFrame({"table": list(counts), "rows": list(counts.values())}))
assert all(n > 0 for n in counts.values()), "A table is empty; ask the trainer."
proved.append("I can count the rows of each table")

# %% [markdown]
# ## Step 4. Group and count
# **What it does:** counts how often each value of one column appears, with `GROUP BY` and `ORDER BY n DESC`, and shows the
# top five.
#
# **Why it matters:** this is the shape of most business questions ("how many loans per status?").
#
# **Try it:** the default uses the first column of your first table. Change `group_column` to the category column you
# spotted in Step 2, and run the cell again.

# %%
first_table = context.bundle.tables[0]
group_column = structure[first_table]["columns"][0]  # change this to a category column from Step 2
summary = tool.run_sql(
    f"SELECT {group_column} AS category, COUNT(*) AS n FROM {first_table} "
    f"GROUP BY {group_column} ORDER BY n DESC LIMIT 5",
    request,
)
display(pd.DataFrame(summary.rows, columns=summary.columns))
assert summary.rows, "The query returned no rows."
proved.append(f"I can group and count ({first_table} by {group_column})")

# %% [markdown]
# ## Step 5. The row limit
# **What it does:** asks for up to 1,000 rows of your first table.
#
# **Why it matters:** the data tool never returns more than 200 rows, whatever the SQL says. It protects the shared
# service, and it means you should summarise (Steps 3 and 4) instead of downloading raw rows.
#
# **Predict first:** how many rows come back?

# %%
try:
    big = tool.run_sql(f"SELECT * FROM {first_table} LIMIT 1000", request)
except ValueError as exc:
    print("The request was refused:", exc)
else:
    print("Rows returned:", len(big.rows))
    display(pd.DataFrame(big.rows, columns=big.columns).head(3))
    assert len(big.rows) <= 200, "The 200-row limit was not applied."
proved.append("I saw that one answer never returns more than 200 rows")

# %% [markdown]
# ## Step 6. A table that is not mine
# **What it does:** asks for a table that exists in the dataset but is not in your mission.
#
# **Why it matters:** access is decided by your group, not by the notebook. The refusal is a normal, friendly message, not
# a crash. Do not try to get around it.
#
# **Look for:** the line that starts with "Unassigned table refused".

# %%
from bni_training.data.engine import RestrictedTableError

all_tables = {"branches", "customers", "accounts", "transactions", "loans"}
outside_table = next(iter(sorted(all_tables - set(context.bundle.tables))), None)
if outside_table:
    try:
        tool.run_sql(f"SELECT * FROM {outside_table} LIMIT 1", request)
    except RestrictedTableError as exc:
        print("Unassigned table refused:", exc)
        proved.append(f"A table outside my mission ({outside_table}) is refused")
    else:
        raise AssertionError("A table outside the mission unexpectedly ran.")
else:
    print("Your mission uses every table, so there is nothing to refuse here.")

# %% [markdown]
# ## Step 7. A command that changes data
# **What it does:** tries `DELETE FROM customers`.
#
# **Why it matters:** the tool only allows one read-only `SELECT`. A write is blocked before it reaches any data, so
# nothing is deleted. Seeing the refusal is the expected result.
#
# **Look for:** the line that starts with "Write refused".

# %%
try:
    tool.run_sql("DELETE FROM customers", request)
except ValueError as exc:
    print("Write refused:", exc)
    proved.append("A command that changes data is refused")
else:
    raise AssertionError("A write unexpectedly ran.")

# %% [markdown]
# ## Step 8. Another group's identity
# **What it does:** builds a request that claims to be a different group and sends it with your tool.
#
# **Why it matters:** your group is fixed for the session. The tool checks the identity before any SQL runs. This
# separation is an application rule for the workshop, not a security boundary.
#
# **Look for:** the line that starts with "Cross-group request refused".

# %%
from bni_training.data.tool import CrossGroupAccessError, DataRequest

other_group = "group_02" if context.group_id != "group_02" else "group_03"
cross_group_request = DataRequest(other_group, "exercise", context.dataset_id, context.mission_id)
try:
    tool.run_sql(f"SELECT COUNT(*) FROM {context.bundle.tables[0]}", cross_group_request)
except CrossGroupAccessError as exc:
    print("Cross-group request refused:", exc)
    proved.append("A request in another group's name is refused")
else:
    raise AssertionError("A cross-group request unexpectedly ran.")

# %% [markdown]
# ## Your turn
# Write one question of your own as a `SELECT`. Use only your tables and the column names from Step 2.
#
# - Easy: count the rows of your second table.
# - Medium: group and count a different column than in Step 4.
# - Hard: show the three largest values of a number column (`ORDER BY <column> DESC LIMIT 3`).
#
# **Predict first:** write down (on paper or in your head) what you expect the answer to look like. Then run the cell.
# The default question is valid for every group, so the cell passes until you change it. Keep it a single `SELECT`.

# %%
# EXERCISE: edit only this SELECT. Keep one statement and only your own tables.
exercise_sql = f"SELECT COUNT(*) AS row_count FROM {context.bundle.tables[0]}"
assert exercise_sql.strip().lower().startswith("select"), "Write a single SELECT statement."
exercise_result = tool.run_sql(exercise_sql, request)
assert exercise_result.rows, "Your question returned no rows; check the column and table names from Step 2."
print(exercise_sql)
display(pd.DataFrame(exercise_result.rows, columns=exercise_result.columns).head(10))
proved.append("I wrote and ran a SQL question of my own")

# %% [markdown]
# ## Save your preview
# **What it does:** writes the table names, columns and sample rows from Steps 2 and 3 as one JSON file in your group's
# output folder.
#
# **Why it matters:** results stay in your own folder. The physical dataset is never copied.

# %%
preview = {
    table: {
        "row_count": counts[table],
        "columns": structure[table]["columns"],
        "sample": structure[table]["sample"],
    }
    for table in context.bundle.tables
}
saved = context.write_output("04_dataset_preview.json", json.dumps(preview, indent=2, default=str))
print({"saved": saved.name, "tables": list(preview)})
proved.append("I saved a preview in my group's output folder")

# %% [markdown]
# ## Closing: what you proved
# The next cell prints one line for every step you completed. If a line is missing, a step did not run: scroll up and
# run it.
#
# ## Expected result
# Ten lines. Your tables and their sizes appear, the refusals are friendly messages, and one preview file is saved.
#
# ## Common errors
# A refused column or table is outside your mission. A refused write is expected. Do not switch to Impala or to another
# group to get around a refusal.
#
# ## Completion checkpoint
# Explain in your own words, to your trainer or a neighbour:
# 1. What is the difference between the one physical dataset and your logical bundle?
# 2. Why does the tool return at most 200 rows?
# 3. Why is the separation between groups called operational and not a security boundary?
#
# ## Reference implementation
# The guarded engine and tool live in `bni_training.data`; `scripts/04_csv_data_access.py` is the automation reference.
#
# ## Cleanup
# The next cell closes the in-memory data engine. Keep the preview file. No shared service was started.

# %%
from bni_training.workshop.notebook_support import lab_status

for number, sentence in enumerate(proved, start=1):
    print(f"{number:>2}. {sentence}")
context.close()
lab_status("04", LAB_MODE, passed=len(proved))
