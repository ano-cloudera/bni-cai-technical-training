"""Read-only analytical access to the synthetic CSV dataset for participants.

The existing SQLite approach is reused (no new service). Defence in depth:

1. The SQL is parsed with sqlglot. Only a single SELECT/WITH statement is accepted.
2. Every table reference must be one of the group's bundle tables. Each is replaced by a sub-query that
   exposes only participant-visible columns and applies the bundle's optional row filter. Raw tables
   (``_raw_*``) can never be named by a user.
3. A SQLite authorizer allows only SELECT/READ/FUNCTION, so no write, ATTACH or PRAGMA can run, and it denies
   reading hidden columns even if the rewrite were bypassed.
4. ``PRAGMA query_only`` is on, results are capped, and a progress handler aborts long-running queries.

This is application-level operational isolation, not a security boundary.
"""

from __future__ import annotations

import csv
import sqlite3
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from sqlglot import exp

from bni_training.schemas import QueryResult
from bni_training.user_errors import UserFacingError

from .dictionary import DEFAULT_RAW_DIR, SQLITE_TYPES, DataDictionary

DEFAULT_MAX_ROWS = 200
DEFAULT_TIMEOUT_S = 10.0
FORBIDDEN_FUNCTIONS = frozenset(
    {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "zipfile", "sqlar_compress"}
)
_WRITE_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Alter, exp.Command, exp.Pragma)
_SQLITE_ALLOWED_ACTIONS = frozenset({sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION})
_SQLITE_RECURSIVE = getattr(sqlite3, "SQLITE_RECURSIVE", 33)


class QueryRejected(UserFacingError):
    """A request was refused. The message is safe and friendly to show to a participant."""


class RestrictedTableError(QueryRejected):
    pass


class RestrictedColumnError(QueryRejected):
    pass


@dataclass(frozen=True)
class AccessPolicy:
    allowed_tables: frozenset[str]
    row_filters: Mapping[str, str] = field(default_factory=dict)


class WorkshopQueryResult(QueryResult):
    truncated: bool = False


def _is_hidden(dictionary: DataDictionary) -> tuple[dict[str, frozenset[str]], frozenset[str]]:
    per_table = {
        name: frozenset(c.name for c in t.columns if not c.participant_exposed)
        for name, t in dictionary.tables.items()
    }
    exposed_anywhere = {c for t in dictionary.tables.values() for c in t.exposed_columns}
    hidden_names = frozenset(c for cols in per_table.values() for c in cols if c not in exposed_anywhere)
    return per_table, hidden_names


class CsvEngine:
    """Loads the CSV files once into memory and answers guarded, read-only queries. Thread-safe."""

    def __init__(self, raw_dir: Path = DEFAULT_RAW_DIR, dictionary: DataDictionary | None = None):
        self.raw_dir = Path(raw_dir)
        self.dictionary = dictionary or DataDictionary.load()
        self._hidden_by_table, self._hidden_names = _is_hidden(self.dictionary)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._load()
        self._conn.execute("PRAGMA query_only = ON")
        self._conn.set_authorizer(self._authorize)
        self._deadline = 0.0

    # loading
    def _load(self) -> None:
        for name, table in self.dictionary.tables.items():
            path = self.raw_dir / f"{name}.csv"
            if not path.is_file():
                raise FileNotFoundError(f"Dataset file not found: {path.name}")
            defs = ", ".join(f'"{c.name}" {SQLITE_TYPES[c.type]}' for c in table.columns)
            self._conn.execute(f'CREATE TABLE "_raw_{name}" ({defs})')
            converters = [
                int if c.type == "integer" else float if c.type == "real" else str for c in table.columns
            ]
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader)
                if tuple(header) != table.column_names:
                    raise ValueError(f"{path.name} does not match the data dictionary")
                placeholders = ",".join("?" for _ in table.columns)
                self._conn.executemany(
                    f'INSERT INTO "_raw_{name}" VALUES ({placeholders})',
                    ([conv(v) for conv, v in zip(converters, row, strict=True)] for row in reader),
                )
            for column in table.columns:
                if column.role in ("primary_key", "foreign_key"):
                    self._conn.execute(
                        f'CREATE INDEX "_ix_{name}_{column.name}" ON "_raw_{name}" ("{column.name}")'
                    )
        self._conn.commit()

    # guards
    def _authorize(self, action, arg1, arg2, _db, _source):
        if action == sqlite3.SQLITE_READ:
            table = (arg1 or "").removeprefix("_raw_")
            if table in self._hidden_by_table and arg2 in self._hidden_by_table[table]:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action in _SQLITE_ALLOWED_ACTIONS or action == _SQLITE_RECURSIVE:
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in FORBIDDEN_FUNCTIONS:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def rewrite(self, sql: str, policy: AccessPolicy) -> str:
        """Validate ``sql`` and return the SQLite text with every table replaced by its guarded sub-query."""
        try:
            statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
        except sqlglot.errors.SqlglotError as exc:
            raise QueryRejected(
                "I could not understand that query. Check the SQL syntax and try again."
            ) from exc
        if len(statements) != 1:
            raise QueryRejected("Send exactly one SELECT query at a time.")
        tree = statements[0]
        if not isinstance(tree, (exp.Select, exp.Union)) or tree.find(*_WRITE_NODES):
            raise QueryRejected("Only read-only SELECT queries are allowed. Writes and commands are blocked.")
        for func in tree.find_all(exp.Func):
            name = (func.name or func.sql_name() or "").lower()
            if name in FORBIDDEN_FUNCTIONS:
                raise QueryRejected(f"The function {name} is not allowed.")
        for column in tree.find_all(exp.Column):
            if column.name in self._hidden_names:
                raise RestrictedColumnError(
                    f"The column '{column.name}' is not available to participants. "
                    "Use the columns listed in the data dictionary for your mission."
                )
        cte_names = {cte.alias.lower() for cte in tree.find_all(exp.CTE)}
        allowed_sorted = ", ".join(sorted(policy.allowed_tables))

        def guard(node: exp.Expression) -> exp.Expression:
            if not isinstance(node, exp.Table):
                return node
            if node.args.get("db") or node.args.get("catalog"):
                raise RestrictedTableError("Schema-qualified table names are not allowed.")
            if not isinstance(node.this, exp.Identifier):
                raise RestrictedTableError("Table functions and file access are not allowed.")
            name = node.name
            if name.lower() in cte_names:
                return node
            if name not in policy.allowed_tables:
                raise RestrictedTableError(
                    f"The table '{name}' is not part of your mission's dataset. "
                    f"You can use: {allowed_sorted}."
                )
            columns = ", ".join(f'"{c}"' for c in self.dictionary.tables[name].exposed_columns)
            where = f" WHERE {policy.row_filters[name]}" if name in policy.row_filters else ""
            inner = sqlglot.parse_one(f'SELECT {columns} FROM "_raw_{name}"{where}', read="sqlite")
            alias = node.alias or name
            return exp.Subquery(this=inner, alias=exp.TableAlias(this=exp.to_identifier(alias)))

        return tree.transform(guard).sql(dialect="sqlite")

    # execution
    def query(
        self,
        sql: str,
        policy: AccessPolicy,
        *,
        max_rows: int = DEFAULT_MAX_ROWS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> WorkshopQueryResult:
        rewritten = self.rewrite(sql, policy)
        started = time.perf_counter()
        with self._lock:
            self._deadline = time.monotonic() + timeout_s
            self._conn.set_progress_handler(lambda: 1 if time.monotonic() > self._deadline else 0, 10_000)
            try:
                cursor = self._conn.execute(rewritten)
                fetched = cursor.fetchmany(max_rows + 1)
                columns = [d[0] for d in cursor.description or []]
            except sqlite3.OperationalError as exc:
                message = str(exc)
                if "interrupted" in message:
                    raise QueryRejected(
                        "That query took too long. Try a simpler question or add a filter."
                    ) from exc
                if "no such column" in message or "not authorized" in message:
                    raise RestrictedColumnError(
                        "One of the columns is not available to your mission. Check the data dictionary."
                    ) from exc
                raise QueryRejected("The query could not be run. Check the table and column names.") from exc
            finally:
                self._conn.set_progress_handler(None, 0)
        truncated = len(fetched) > max_rows
        rows = [list(r) for r in fetched[:max_rows]]
        return WorkshopQueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed_ms=(time.perf_counter() - started) * 1000,
            truncated=truncated,
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
