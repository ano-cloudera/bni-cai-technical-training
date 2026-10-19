from __future__ import annotations

import pytest

from bni_training.data.semantic_layer import DimensionNotAvailable, MetricNotAvailable, NoMetricFound

REQUIRED_METRICS = {
    "total_customers", "active_customers", "total_accounts", "active_accounts", "dormant_accounts",
    "total_balance", "average_account_balance", "transaction_count", "transaction_amount",
    "average_transaction_amount", "digital_transaction_ratio", "total_loans", "total_outstanding",
    "delinquent_loans", "delinquency_ratio", "product_adoption_rate", "branch_customer_count",
    "branch_transaction_amount",
}  # fmt: skip


def test_all_required_metrics_exist(semantic) -> None:
    assert REQUIRED_METRICS <= set(semantic.metrics)
    for metric in semantic.metrics.values():
        assert metric.description.strip() and metric.expression.strip()


@pytest.mark.parametrize("name", sorted(REQUIRED_METRICS))
def test_every_metric_runs_and_produces_a_valid_number(semantic, engine, everything, name) -> None:
    plan = semantic.plan(name, (), allowed_tables=everything.allowed_tables)
    result = engine.query(plan.sql, everything)
    assert result.row_count == 1
    value = result.rows[0][0]
    assert isinstance(value, (int, float)) and value >= 0
    if name.endswith("_ratio") or name in ("product_adoption_rate",):
        assert 0 <= value <= 1
    assert plan.sql.upper().startswith("SELECT") and "LIMIT" in plan.sql


def test_metric_values_agree_with_the_raw_files(semantic, engine, everything) -> None:
    import csv

    from bni_training.data.dictionary import DEFAULT_RAW_DIR

    def run(name, *dims):
        return engine.query(
            semantic.plan(name, dims, allowed_tables=everything.allowed_tables).sql, everything
        )

    with (DEFAULT_RAW_DIR / "accounts.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert run("total_accounts").rows[0][0] == len(rows)
    assert run("dormant_accounts").rows[0][0] == sum(r["account_status"] == "DORMANT" for r in rows)
    assert abs(run("total_balance").rows[0][0] - sum(float(r["balance"]) for r in rows)) < 1.0
    by_type = dict(run("total_accounts", "account_type").rows)
    assert sum(by_type.values()) == len(rows)


def test_joins_follow_parents_only_so_breakdowns_never_double_count(semantic, engine, everything) -> None:
    for metric, dimension in (
        ("total_accounts", "segment"), ("transaction_count", "region"), ("total_loans", "region"),
        ("transaction_amount", "segment"), ("total_loans", "segment"),
    ):  # fmt: skip
        plain = engine.query(
            semantic.plan(metric, (), allowed_tables=everything.allowed_tables).sql, everything
        ).rows[0][0]
        rows = engine.query(
            semantic.plan(metric, (dimension,), allowed_tables=everything.allowed_tables, limit=200).sql,
            everything,
        ).rows
        assert abs(sum(r[1] for r in rows) - plain) < 1e-6 * max(plain, 1), (metric, dimension)


def test_dimension_source_prefers_the_metrics_own_table(semantic, everything) -> None:
    sql = semantic.plan("total_loans", ("product_code",), allowed_tables=everything.allowed_tables).sql
    assert "loans.product_code" in sql and "accounts.product_code" not in sql
    assert (
        "branches.region"
        in semantic.plan("total_accounts", ("region",), allowed_tables=everything.allowed_tables).sql
    )
    assert (
        "customers.region"
        in semantic.plan("total_accounts", ("region",), allowed_tables={"accounts", "customers"}).sql
    )


def test_a_breakdown_that_needs_a_table_outside_the_bundle_is_refused(semantic) -> None:
    with pytest.raises(DimensionNotAvailable, match="cannot be broken down"):
        semantic.plan("transaction_count", ("segment",), allowed_tables={"transactions", "accounts"})
    with pytest.raises(MetricNotAvailable, match="needs the table"):
        semantic.plan("total_loans", (), allowed_tables={"customers", "accounts"})
    with pytest.raises(MetricNotAvailable, match="not part of your mission"):
        semantic.plan("total_loans", (), allowed_tables={"loans"}, allowed_metrics={"total_customers"})
    with pytest.raises(DimensionNotAvailable):
        semantic.plan("total_customers", ("product_code",), allowed_tables={"customers", "accounts"})


@pytest.mark.parametrize(
    "question, metric, dims",
    [
        ("Show total customers by segment", "total_customers", ["segment"]),
        ("How many active customers by region?", "active_customers", ["region"]),
        (
            "Show transaction count by account id and transaction date top 20",
            "transaction_count",
            ["account_id", "transaction_date"],
        ),
        ("Show delinquency ratio by product code", "delinquency_ratio", ["product_code"]),
        ("Show branch transaction amount by branch name top 5", "branch_transaction_amount", ["branch_name"]),
        ("Show total balance", "total_balance", []),
    ],
)  # fmt: skip
def test_questions_resolve_to_the_expected_metric_and_dimensions(
    semantic, everything, question, metric, dims
) -> None:
    plan = semantic.resolve_question(
        question, allowed_tables=everything.allowed_tables, allowed_metrics=set(semantic.metrics)
    )
    assert plan.metric == metric and list(plan.dimensions) == dims


def test_top_n_means_highest_first_and_dates_default_to_chronological_order(semantic, everything) -> None:
    allowed = {"allowed_tables": everything.allowed_tables, "allowed_metrics": set(semantic.metrics)}
    ranked = semantic.resolve_question(
        "Show transaction count by account id and transaction date top 20", **allowed
    )
    assert "ORDER BY transaction_count DESC" in ranked.sql and ranked.sql.endswith("LIMIT 20")
    monthly = semantic.resolve_question("Show transaction amount by month", **allowed)
    assert "ORDER BY substr(transactions.transaction_date, 1, 7)" in monthly.sql


def test_unclear_questions_get_helpful_errors(semantic, everything) -> None:
    allowed = {
        "allowed_tables": everything.allowed_tables,
        "allowed_metrics": {"total_customers", "total_accounts"},
    }
    with pytest.raises(NoMetricFound, match="Try one of"):
        semantic.resolve_question("Tell me a joke", **allowed)
    with pytest.raises(MetricNotAvailable):
        semantic.resolve_question("Show total loans", **allowed)
    with pytest.raises(DimensionNotAvailable, match="breakdown"):
        semantic.resolve_question("Show total customers by the weather", **allowed)


def test_business_terms_cover_the_required_definitions(semantic) -> None:
    required = {
        "active customer", "active account", "dormant account", "transaction amount", "digital transaction",
        "outstanding amount", "delinquent loan", "days past due", "product adoption", "branch performance",
        "unusual transaction pattern",
    }  # fmt: skip
    assert required <= set(semantic.terms)
