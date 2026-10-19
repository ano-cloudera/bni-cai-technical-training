"""Participants may only reach the tables and metrics of their own logical bundle (operational isolation)."""

from __future__ import annotations

import pytest

from bni_training.data.bundles import BundleCatalog
from bni_training.data.engine import RestrictedColumnError, RestrictedTableError
from bni_training.data.semantic_layer import DimensionNotAvailable, MetricNotAvailable
from bni_training.data.tool import CrossGroupAccessError, DataRequest, WorkshopDataTool

TABLES = ("branches", "customers", "accounts", "transactions", "loans")
GROUPS = [f"group_{i:02d}" for i in range(1, 11)]
CATALOG = BundleCatalog.load()
RESTRICTED = [(g, t) for g in GROUPS for t in TABLES if t not in CATALOG.for_group(g).tables]


@pytest.fixture(scope="module")
def tools(engine, semantic):
    return {g: WorkshopDataTool(engine, semantic, CATALOG.for_group(g)) for g in GROUPS}


def test_there_are_restricted_tables_to_test() -> None:
    assert len(RESTRICTED) == 50 - sum(len(CATALOG.for_group(g).tables) for g in GROUPS)
    assert len(RESTRICTED) >= 15


@pytest.mark.parametrize("group_id, table", RESTRICTED)
def test_a_group_cannot_query_a_table_outside_its_bundle(tools, group_id, table) -> None:
    for sql in (
        f"SELECT * FROM {table} LIMIT 1",
        f"SELECT COUNT(*) FROM {table}",
        f"SELECT 1 WHERE EXISTS (SELECT 1 FROM {table})",
    ):
        with pytest.raises(RestrictedTableError, match="not part of your mission"):
            tools[group_id].run_sql(sql)


@pytest.mark.parametrize("group_id", GROUPS)
def test_a_group_can_query_every_table_of_its_own_bundle(tools, group_id) -> None:
    for table in CATALOG.for_group(group_id).tables:
        assert tools[group_id].run_sql(f"SELECT COUNT(*) AS n FROM {table}").rows[0][0] > 0


@pytest.mark.parametrize("group_id", GROUPS)
def test_a_group_cannot_use_a_metric_outside_its_bundle(tools, semantic, group_id) -> None:
    bundle = CATALOG.for_group(group_id)
    for metric in set(semantic.metrics) - set(bundle.allowed_metrics):
        question = f"Show {metric.replace('_', ' ')}"
        with pytest.raises((MetricNotAvailable, DimensionNotAvailable)):
            tools[group_id].query(question)


@pytest.mark.parametrize("group_id", [g for g in GROUPS if "transactions" in CATALOG.for_group(g).tables])
def test_the_hidden_anomaly_column_is_unreachable_for_every_group_with_transactions(tools, group_id) -> None:
    for sql in (
        "SELECT is_seeded_anomaly FROM transactions",
        "SELECT * FROM transactions WHERE is_seeded_anomaly = 1",
        "SELECT t.is_seeded_anomaly FROM transactions t",
    ):
        with pytest.raises(RestrictedColumnError):
            tools[group_id].run_sql(sql)
    assert "is_seeded_anomaly" not in tools[group_id].run_sql("SELECT * FROM transactions LIMIT 1").columns


def test_a_request_naming_another_groups_bundle_is_rejected_for_every_pair(tools) -> None:
    for owner in GROUPS:
        for other in GROUPS:
            if owner == other:
                continue
            b = CATALOG.for_group(other)
            forged = DataRequest(owner, "a" * 32, b.dataset_id, b.mission_id)
            with pytest.raises(CrossGroupAccessError):
                tools[owner].run_sql("SELECT 1", forged)


def test_participants_cannot_reach_files_the_engine_or_the_operating_system(tools) -> None:
    attempts = (
        "SELECT * FROM '/etc/passwd'",
        "SELECT readfile('/etc/passwd')",
        "SELECT load_extension('x')",
        "ATTACH DATABASE '/tmp/x.db' AS x",
        "SELECT * FROM pragma_table_info('customers')",
    )
    for sql in attempts:
        with pytest.raises(Exception) as error:
            tools["group_10"].run_sql(sql)
        assert type(error.value).__name__ in (
            "QueryRejected",
            "RestrictedTableError",
            "RestrictedColumnError",
        )


def test_every_result_is_row_capped(tools) -> None:
    result = tools["group_10"].run_sql("SELECT * FROM transactions")
    assert result.row_count == 200 and result.truncated is True


def test_isolation_is_documented_as_operational_not_security() -> None:
    from pathlib import Path

    for path in ("data/README.md", "src/bni_training/data/engine.py", "apps/workshop-portal/README.md"):
        assert "security boundary" in Path(path).read_text(), path
