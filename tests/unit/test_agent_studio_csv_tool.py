import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("csv_data_tool", ROOT / "deployments/agent-studio/csv_data_tool/tool.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def run(bundle, query):
    config = tool.UserParameters(csv_dir=str(ROOT / "data/raw"), bundle_id=bundle)
    return tool.run_tool(config, tool.ToolParameters(query=query))


def test_schema_lists_only_the_bundle_tables():
    result = run("loan_monitoring_bundle", "schema")
    assert set(result["tables"]) == {"loans", "customers", "accounts"}
    assert "delinquency_ratio" in result["allowed_metrics"]


def test_a_select_returns_rows_with_a_default_limit():
    result = run("loan_monitoring_bundle", "SELECT loan_status, COUNT(*) AS n FROM loans GROUP BY loan_status")
    assert result["row_count"] > 0 and result["sql"].upper().endswith("LIMIT 100")


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM transactions",
        "DROP TABLE loans",
        "SELECT * FROM loans; SELECT * FROM customers",
        "SELECT * FROM loans -- hide",
        "UPDATE loans SET risk_band = 'LOW'",
        "SELECT * FROM sqlite_master",
    ],
)
def test_forbidden_queries_return_an_error_and_no_rows(query):
    result = run("loan_monitoring_bundle", query)
    assert "error" in result and "rows" not in result


def test_a_row_filter_cannot_be_skipped():
    result = run("branch_performance_bundle", "SELECT DISTINCT operational_status FROM branches")
    assert [row[0] for row in result["rows"]] != [] and all(row[0] != "CLOSED" for row in result["rows"])


def test_an_unknown_bundle_is_refused_with_an_error_not_a_traceback():
    result = run("no_such_bundle", "schema")
    assert "error" in result and "Unknown bundle_id" in result["error"] and "diagnostics" in result


def test_a_folder_the_sandbox_cannot_see_returns_diagnostics_instead_of_a_traceback(tmp_path):
    config = tool.UserParameters(csv_dir=str(tmp_path / "missing" / "raw"), bundle_id="loan_monitoring_bundle")
    result = tool.run_tool(config, tool.ToolParameters(query="schema"))
    assert "FileNotFoundError" in result["error"]
    diagnostics = result["diagnostics"]
    assert diagnostics["csv_dir_exists"] is False and "working_directory" in diagnostics and "root_entries" in diagnostics


def test_the_bundle_file_may_sit_in_the_same_folder_as_the_csv_files(tmp_path):
    import shutil

    for name in ("loans.csv", "customers.csv", "accounts.csv"):
        shutil.copy(ROOT / "data/raw" / name, tmp_path / name)
    shutil.copy(ROOT / "data/scenarios/dataset_bundles.yaml", tmp_path / "dataset_bundles.yaml")
    config = tool.UserParameters(csv_dir=str(tmp_path), bundle_id="loan_monitoring_bundle")
    result = tool.run_tool(config, tool.ToolParameters(query="SELECT COUNT(*) AS n FROM loans"))
    assert result["rows"] == [[5000]]


def test_the_workflow_data_mount_is_used_when_the_configured_folder_is_missing(tmp_path, monkeypatch):
    import shutil

    data = tmp_path / "workflow_data" / "data"
    (data / "raw").mkdir(parents=True)
    (data / "scenarios").mkdir()
    for name in ("loans.csv", "customers.csv", "accounts.csv"):
        shutil.copy(ROOT / "data/raw" / name, data / "raw" / name)
    shutil.copy(ROOT / "data/scenarios/dataset_bundles.yaml", data / "scenarios" / "dataset_bundles.yaml")
    monkeypatch.setenv("WORKFLOW_DATA_DIRECTORY", str(tmp_path / "workflow_data"))
    config = tool.UserParameters(csv_dir="/does/not/exist/raw", bundle_id="loan_monitoring_bundle")
    result = tool.run_tool(config, tool.ToolParameters(query="SELECT COUNT(*) AS n FROM loans"))
    assert result["rows"] == [[5000]]


def test_diagnostics_list_the_mount_points_a_sandbox_can_have():
    config = tool.UserParameters(csv_dir="/does/not/exist/raw", bundle_id="x")
    keys = tool._diagnostics(config).keys()
    assert {"workflow_data_entries", "tool_entries", "root_entries", "home_entries", "workspace_entries"} <= set(keys)
