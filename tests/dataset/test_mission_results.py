from __future__ import annotations

import json

import pytest

from bni_training.data.bundles import BundleCatalog
from bni_training.data.dictionary import DEFAULT_MANIFEST_DIR
from bni_training.data.tool import WorkshopDataTool
from bni_training.data.validation import LARGE_AMOUNT_SQL, STRUCTURING_SQL

GROUPS = [f"group_{i:02d}" for i in range(1, 11)]


@pytest.fixture(scope="module")
def catalog() -> BundleCatalog:
    return BundleCatalog.load()


@pytest.fixture(scope="module")
def tools(engine, semantic, catalog):
    return {g: WorkshopDataTool(engine, semantic, catalog.for_group(g)) for g in GROUPS}


@pytest.mark.parametrize("group_id", GROUPS)
def test_every_sample_question_of_every_mission_returns_meaningful_results(tools, catalog, group_id) -> None:
    for question in catalog.for_group(group_id).sample_questions:
        sql, result = tools[group_id].query(question)
        assert result.row_count > 0 and result.columns, (group_id, question)
        assert sql.startswith("SELECT"), sql
        metric_column = result.columns[-1]
        values = [row[-1] for row in result.rows]
        assert all(isinstance(v, (int, float)) and v >= 0 for v in values), (question, metric_column)
        assert len({tuple(r) for r in result.rows}) == result.row_count, "no duplicated result rows"


@pytest.mark.parametrize("group_id", GROUPS)
def test_every_allowed_metric_of_every_group_runs_inside_the_group_bundle(
    tools, catalog, semantic, engine, group_id
) -> None:
    bundle = catalog.for_group(group_id)
    for metric in bundle.allowed_metrics:
        plan = semantic.plan(metric, (), allowed_tables=bundle.tables, allowed_metrics=bundle.allowed_metrics)
        result = engine.query(plan.sql, bundle.policy)
        assert result.row_count == 1 and result.rows[0][0] >= 0, (group_id, metric)


def test_mission_results_differ_between_missions(tools) -> None:
    firsts = {g: tuple(map(tuple, tools[g].query(c.sample_questions[0])[1].rows)) for g, c in
              ((g, tools[g].bundle) for g in GROUPS)}  # fmt: skip
    assert len(set(firsts.values())) == 10


def test_the_branch_mission_never_sees_closed_branches_but_the_regional_mission_does(tools) -> None:
    sql = "SELECT COUNT(*) FROM branches"
    assert tools["group_04"].run_sql(sql).rows[0][0] == 98
    assert tools["group_09"].run_sql(sql).rows[0][0] == 100
    ranked = tools["group_04"].query("Show branch customer count by branch name top 100")[1]
    assert ranked.row_count <= 98


def anomaly_accounts() -> dict[str, set[str]]:
    by_type: dict[str, set[str]] = {}
    for incident in json.loads((DEFAULT_MANIFEST_DIR / "anomaly_test_manifest.json").read_text())[
        "incidents"
    ]:
        by_type.setdefault(incident["type"], set()).add(incident["account_id"])
    return by_type


def test_group_06_can_discover_every_kind_of_seeded_unusual_pattern(tools) -> None:
    seeded = anomaly_accounts()
    tool = tools["group_06"]
    top = {r[0] for r in tool.query(tool.bundle.sample_questions[0])[1].rows}
    assert len(top & seeded["velocity_burst"]) >= 8, "daily bursts surface in the first sample question"
    large = {r[0] for r in tool.run_sql(LARGE_AMOUNT_SQL).rows}
    assert len(large & seeded["large_amount"]) >= 13 and len(large - set().union(*seeded.values())) < 40
    structuring = {r[0] for r in tool.run_sql(STRUCTURING_SQL).rows}
    assert len(structuring & seeded["structuring"]) >= 7


def test_the_default_participant_tool_never_exposes_the_anomaly_flag(tools) -> None:
    tool = tools["group_06"]
    assert "is_seeded_anomaly" not in json.dumps(tool.describe())
    assert "is_seeded_anomaly" not in tool.run_sql("SELECT * FROM transactions LIMIT 1").columns
