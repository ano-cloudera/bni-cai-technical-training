"""
Read the synthetic banking CSV files for ONE workshop dataset bundle.

Use this tool to answer a business question with numbers. Call it first with query="schema" to see the
tables, columns and rows the bundle allows. Then call it with one read-only SQL query (SELECT or WITH) over
those tables. Only the first rows are returned; every number in your answer must come from the returned rows.
The data is fully synthetic. The tool cannot change anything and cannot read tables outside the bundle.
"""

import argparse
import csv
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

DEFAULT_LIMIT = 100
MAX_LIMIT = 200
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|call|attach|detach|pragma|replace|vacuum)\b",
    re.I,
)
TABLE_REFERENCE = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", re.I)


class UserParameters(BaseModel):
    """
    Where the data is and which bundle this agent may use. Set these once when you add the tool to a workflow.
    """
    csv_dir: str  # Folder with the CSV files, for example the data/raw folder of the repository.
    bundle_id: str  # One bundle name from dataset_bundles.yaml, for example loan_monitoring_bundle.
    bundles_file: Optional[str] = None  # Path to dataset_bundles.yaml. Default: ../scenarios/dataset_bundles.yaml next to csv_dir.


class ToolParameters(BaseModel):
    """
    What the agent sends on each call.
    """
    query: str = Field(
        description=(
            "Either the word schema (to list the allowed tables, columns and metrics), or ONE read-only SQL query "
            "(SELECT or WITH) over the allowed tables. Do not use comments or several statements."
        )
    )


def _bundle(config: UserParameters) -> tuple[dict, Path]:
    csv_dir = Path(config.csv_dir).expanduser().resolve()
    if config.bundles_file:
        candidates = [Path(config.bundles_file).expanduser()]
    else:
        candidates = [csv_dir.parent / "scenarios" / "dataset_bundles.yaml", csv_dir / "dataset_bundles.yaml"]
    bundles_path = next((path for path in candidates if path.is_file()), None)
    if bundles_path is None:
        raise FileNotFoundError("dataset_bundles.yaml was not found; set bundles_file in the tool configuration")
    bundles = yaml.safe_load(bundles_path.read_text(encoding="utf-8")).get("bundles", {})
    if config.bundle_id not in bundles:
        raise ValueError("Unknown bundle_id. Choose one of: " + ", ".join(sorted(bundles)))
    return bundles[config.bundle_id], csv_dir


def _names(path: str, limit: int = 25) -> Any:
    """Entry names of a folder, or why it cannot be listed. Names only; no file content."""
    try:
        return sorted(os.listdir(path))[:limit]
    except OSError as exc:
        return f"not readable: {type(exc).__name__}"


def _diagnostics(config: UserParameters) -> dict:
    """What this sandbox can see, so a missing-file error can be fixed without guessing."""
    csv_dir = Path(config.csv_dir).expanduser()
    return {
        "working_directory": os.getcwd(),
        "csv_dir": str(csv_dir),
        "csv_dir_exists": csv_dir.is_dir(),
        "csv_dir_entries": _names(str(csv_dir)) if csv_dir.is_dir() else "missing",
        "root_entries": _names("/"),
        "working_directory_entries": _names(os.getcwd()),
        "workspace_entries": _names("/workspace") if os.path.isdir("/workspace") else "missing",
    }


def _load(spec: dict, csv_dir: Path) -> sqlite3.Connection:
    """In-memory database that holds only the bundle's tables; row filters become views so the agent cannot skip them."""
    connection = sqlite3.connect(":memory:")
    filters = spec.get("row_filters") or {}
    for table in spec["tables"]:
        path = csv_dir / f"{table}.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            columns = next(reader)
            raw_name = f"{table}__all" if table in filters else table
            connection.execute(f'CREATE TABLE "{raw_name}" ({", ".join(chr(34) + c + chr(34) for c in columns)})')
            connection.executemany(
                f'INSERT INTO "{raw_name}" VALUES ({", ".join("?" * len(columns))})', reader
            )
        if table in filters:
            connection.execute(f'CREATE VIEW "{table}" AS SELECT * FROM "{raw_name}" WHERE {filters[table]}')
    return connection


def _schema(connection: sqlite3.Connection, spec: dict) -> dict:
    tables = {}
    for table in spec["tables"]:
        info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        tables[table] = [row[1] for row in info]
    return {
        "tables": tables,
        "allowed_metrics": spec.get("allowed_metrics", []),
        "note": "Values are stored as text. Use CAST(column AS REAL) for numbers. Dates look like 2025-06-10.",
    }


def _validate(sql: str, allowed_tables: set) -> str:
    text = sql.strip().rstrip(";").strip()
    if not re.match(r"^(select|with)\b", text, re.I):
        raise ValueError("Only SELECT or WITH queries are allowed")
    if "--" in text or "/*" in text or "*/" in text:
        raise ValueError("SQL comments are not allowed")
    if ";" in text:
        raise ValueError("Only one SQL statement is allowed")
    if FORBIDDEN.search(text):
        raise ValueError("Only read-only queries are allowed")
    cte_names = {m.lower() for m in re.findall(r"\b(\w+)\s+as\s*\(", text, re.I)}
    used = {name.split(".")[-1].lower() for name in TABLE_REFERENCE.findall(text)} - cte_names
    unknown = used - {table.lower() for table in allowed_tables}
    if unknown:
        raise ValueError("Table is not allowed for this bundle: " + ", ".join(sorted(unknown)))
    if not re.search(r"\blimit\s+\d+\b", text, re.I):
        text += f" LIMIT {DEFAULT_LIMIT}"
    return text


def run_tool(config: UserParameters, args: ToolParameters) -> Any:
    """
    Main tool logic. Anything returned from this method is returned to the calling agent.
    """
    try:
        spec, csv_dir = _bundle(config)
        connection = _load(spec, csv_dir)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "diagnostics": _diagnostics(config)}
    try:
        if args.query.strip().lower() in {"schema", "describe", "tables"}:
            return _schema(connection, spec)
        sql = _validate(args.query, set(spec["tables"]))
        cursor = connection.execute(sql)
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchmany(MAX_LIMIT + 1)
        truncated = len(rows) > MAX_LIMIT
        rows = [list(row) for row in rows[:MAX_LIMIT]]
        return {"sql": sql, "columns": columns, "rows": rows, "row_count": len(rows), "truncated": truncated}
    except (ValueError, sqlite3.Error) as exc:
        return {"error": str(exc), "hint": 'Call this tool with query="schema" to see the allowed tables and columns.'}
    finally:
        connection.close()


OUTPUT_KEY = "tool_output"
"""
Only the stdout after OUTPUT_KEY is passed to the agent, so the structured result below is all the agent sees.
"""


if __name__ == "__main__":
    """
    Tool entrypoint. Agent Studio passes --user-params and --tool-params as JSON strings.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-params", required=True, help="Tool configuration")
    parser.add_argument("--tool-params", required=True, help="Tool arguments")
    args = parser.parse_args()

    config = UserParameters(**json.loads(args.user_params))
    params = ToolParameters(**json.loads(args.tool_params))

    print(OUTPUT_KEY, run_tool(config, params))
