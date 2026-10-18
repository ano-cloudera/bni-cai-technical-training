from __future__ import annotations

import csv
import sqlite3
import time
from pathlib import Path

from bni_training.schemas import HealthStatus, QueryResult


class CsvBackend:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"CSV_DATA_DIR does not exist: {self.data_dir}")
        self._connection = sqlite3.connect(":memory:")
        self._load_csv_files()

    def _load_csv_files(self) -> None:
        for path in sorted(self.data_dir.glob("*.csv")):
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            if not rows:
                continue
            columns = list(rows[0])
            defs = ", ".join(f'"{c}" NUMERIC' for c in columns)
            self._connection.execute(f'CREATE TABLE "{path.stem}" ({defs})')
            placeholders = ",".join("?" for _ in columns)
            self._connection.executemany(
                f'INSERT INTO "{path.stem}" VALUES ({placeholders})',
                [[row[c] for c in columns] for row in rows],
            )

    def execute(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        start = time.perf_counter()
        cursor = self._connection.execute(sql)
        rows = [list(row) for row in cursor.fetchall()]
        columns = [item[0] for item in cursor.description or []]
        return QueryResult(
            columns=columns, rows=rows, row_count=len(rows), elapsed_ms=(time.perf_counter() - start) * 1000
        )

    def healthcheck(self) -> HealthStatus:
        self._connection.execute("SELECT 1")
        return HealthStatus(healthy=True, service="csv", detail=str(self.data_dir))
