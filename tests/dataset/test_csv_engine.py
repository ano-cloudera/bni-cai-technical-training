from __future__ import annotations

import pytest

from bni_training.data.engine import AccessPolicy, QueryRejected, RestrictedColumnError, RestrictedTableError

HIDDEN_COLUMN = "merchant_category"  # hidden only in the hidden_engine fixture


def policy(*tables, **filters) -> AccessPolicy:
    return AccessPolicy(frozenset(tables), filters)


def test_select_and_with_queries_run_and_return_rows(engine) -> None:
    p = policy("customers", "accounts")
    result = engine.query("SELECT segment, COUNT(*) AS n FROM customers GROUP BY segment ORDER BY n DESC", p)
    assert result.columns == ["segment", "n"] and result.row_count == 5
    cte = engine.query(
        "WITH t AS (SELECT region FROM customers) SELECT region, COUNT(*) FROM t GROUP BY region", p
    )
    assert cte.row_count == 6


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "INSERT INTO customers (customer_id) VALUES ('x')",
        "UPDATE customers SET segment = 'X'",
        "DROP TABLE customers",
        "CREATE TABLE x (a int)",
        "ALTER TABLE customers ADD COLUMN x int",
        "PRAGMA table_info(customers)",
        "ATTACH DATABASE 'x.db' AS x",
        "SELECT 1; SELECT 2",
        "SELECT 1; DROP TABLE customers",
        "VACUUM",
    ],
)
def test_writes_and_commands_are_rejected_with_a_friendly_message(engine, sql) -> None:
    with pytest.raises(QueryRejected) as error:
        engine.query(sql, policy("customers"))
    assert "Traceback" not in str(error.value) and len(str(error.value)) < 200


def test_tables_outside_the_bundle_are_rejected(engine) -> None:
    p = policy("customers", "accounts")
    for sql in (
        "SELECT * FROM transactions",
        "SELECT * FROM customers JOIN loans ON loans.customer_id = customers.customer_id",
        "SELECT * FROM (SELECT * FROM loans)",
        "SELECT * FROM customers WHERE customer_id IN (SELECT customer_id FROM loans)",
    ):
        with pytest.raises(RestrictedTableError, match="not part of your mission"):
            engine.query(sql, p)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM _raw_customers",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM main.customers",
        "SELECT * FROM json_each('[1]')",
        "SELECT load_extension('x')",
        "SELECT * FROM '/etc/passwd'",
    ],
)
def test_internal_tables_files_and_functions_are_unreachable(engine, sql) -> None:
    with pytest.raises(QueryRejected):
        engine.query(sql, policy("customers"))


def test_hidden_columns_cannot_be_read_even_with_select_star(hidden_engine) -> None:
    p = policy("transactions")
    with pytest.raises(RestrictedColumnError):
        hidden_engine.query(f"SELECT {HIDDEN_COLUMN} FROM transactions", p)
    with pytest.raises(RestrictedColumnError):
        hidden_engine.query(f"SELECT COUNT(*) FROM transactions WHERE {HIDDEN_COLUMN} = 'NONE'", p)
    star = hidden_engine.query("SELECT * FROM transactions LIMIT 3", p)
    assert HIDDEN_COLUMN not in star.columns and len(star.columns) == 7


def test_the_shipped_dictionary_exposes_every_column_and_no_answer_column_exists(engine) -> None:
    star = engine.query("SELECT * FROM transactions LIMIT 1", policy("transactions"))
    assert len(star.columns) == 8 and not any("anomal" in c or "seeded" in c for c in star.columns)


def test_row_filters_are_applied_inside_every_reference(engine) -> None:
    everything = engine.query("SELECT COUNT(*) FROM branches", policy("branches")).rows[0][0]
    filtered_policy = policy("branches", branches="operational_status <> 'CLOSED'")
    filtered = engine.query("SELECT COUNT(*) FROM branches", filtered_policy).rows[0][0]
    assert filtered < everything
    via_join = engine.query(
        "SELECT COUNT(*) FROM branches b JOIN branches c ON c.branch_id = b.branch_id", filtered_policy
    ).rows[0][0]
    assert via_join == filtered
    closed = engine.query(
        "SELECT COUNT(*) FROM branches WHERE operational_status = 'CLOSED'", filtered_policy
    )
    assert closed.rows[0][0] == 0


def test_results_are_capped_and_marked_truncated(engine) -> None:
    result = engine.query("SELECT * FROM transactions", policy("transactions"), max_rows=25)
    assert result.row_count == 25 and result.truncated is True
    small = engine.query("SELECT * FROM branches", policy("branches"), max_rows=500)
    assert small.truncated is False


def test_runaway_queries_are_stopped(engine) -> None:
    sql = (
        "SELECT COUNT(*) FROM transactions a, transactions b, transactions c "
        "WHERE a.amount + b.amount > c.amount"
    )
    with pytest.raises(QueryRejected, match="too long"):
        engine.query(sql, policy("transactions"), timeout_s=0.2)


def test_the_database_cannot_be_modified_even_if_the_guard_were_bypassed(engine, hidden_engine) -> None:
    import sqlite3

    with pytest.raises(sqlite3.DatabaseError):
        engine._conn.execute('DELETE FROM "_raw_branches"')
    with pytest.raises(sqlite3.DatabaseError):
        hidden_engine._conn.execute(f'SELECT "{HIDDEN_COLUMN}" FROM "_raw_transactions"')
    assert engine.query("SELECT COUNT(*) FROM branches", policy("branches")).rows[0][0] == 100
