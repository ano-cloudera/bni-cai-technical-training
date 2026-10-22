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


def test_an_unknown_bundle_is_refused():
    with pytest.raises(ValueError):
        run("no_such_bundle", "schema")
