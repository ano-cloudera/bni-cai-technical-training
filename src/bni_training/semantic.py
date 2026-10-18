from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .schemas import SemanticQuery


@dataclass(frozen=True)
class SemanticCatalog:
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "SemanticCatalog":
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")))

    @property
    def allowed_tables(self) -> set[str]:
        return set(self.raw["allowed_tables"])


def resolve_question(question: str, catalog: SemanticCatalog, llm=None) -> SemanticQuery:
    lowered = question.lower()
    metric = next((name for name in catalog.raw["metrics"] if name.replace("_", " ") in lowered), None)
    if metric is None:
        metric = next(
            (target for alias, target in catalog.raw.get("synonyms", {}).items() if alias in lowered),
            "account_count",
        )
    dimensions = [name for name in catalog.raw["dimensions"] if name.replace("_", " ") in lowered]
    return SemanticQuery(metric=metric, dimensions=dimensions, limit=100)


def compile_query(query: SemanticQuery, catalog: SemanticCatalog) -> str:
    metric = catalog.raw["metrics"].get(query.metric)
    if not metric:
        raise ValueError(f"Unknown metric: {query.metric}")
    columns = [catalog.raw["dimensions"][d]["column"] for d in query.dimensions]
    select = ", ".join(columns + [f"{metric['expression']} AS {query.metric}"])
    sql = f"SELECT {select} FROM {catalog.raw['base_table']}"
    if columns:
        sql += " GROUP BY " + ", ".join(columns)
    return sql


def compile_question(question: str, catalog: SemanticCatalog) -> str:
    return compile_query(resolve_question(question, catalog), catalog)
