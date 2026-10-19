"""Small semantic layer over the synthetic dataset: metrics, dimensions, joins, and question matching."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from bni_training.user_errors import UserFacingError

from .dictionary import SEMANTIC_DIR

MAX_DIMENSIONS = 2


class SemanticError(UserFacingError):
    """The question cannot be answered by the semantic layer. The message is safe for participants."""


class MetricNotAvailable(SemanticError):
    pass


class DimensionNotAvailable(SemanticError):
    pass


class NoMetricFound(SemanticError):
    pass


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    base_table: str
    expression: str
    where: str | None
    requires: tuple[str, ...]
    synonyms: tuple[str, ...]

    @property
    def tables(self) -> frozenset[str]:
        return frozenset({self.base_table, *self.requires})

    @property
    def phrases(self) -> tuple[str, ...]:
        return (self.name.replace("_", " "), *self.synonyms)


@dataclass(frozen=True)
class DimensionSource:
    table: str
    column: str | None = None
    expression: str | None = None

    @property
    def sql(self) -> str:
        return self.expression or f"{self.table}.{self.column}"


@dataclass(frozen=True)
class Dimension:
    name: str
    description: str
    sources: tuple[DimensionSource, ...]
    synonyms: tuple[str, ...]
    ordered_by_dimension: bool

    @property
    def phrases(self) -> tuple[str, ...]:
        return (self.name.replace("_", " "), *self.synonyms)


@dataclass(frozen=True)
class Join:
    table: str
    on: str


@dataclass(frozen=True)
class PlannedQuery:
    sql: str
    metric: str
    dimensions: tuple[str, ...]
    tables: frozenset[str]


@dataclass
class SemanticModel:
    metrics: dict[str, Metric]
    dimensions: dict[str, Dimension]
    parents: dict[str, list[tuple[str, str, str]]]  # child -> [(child_col, parent_table, parent_col)]
    terms: dict[str, str]
    default_limit: int = 50
    max_limit: int = 200
    _phrase_cache: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, directory: Path = SEMANTIC_DIR) -> SemanticModel:
        directory = Path(directory)
        raw = yaml.safe_load((directory / "metrics.yaml").read_text(encoding="utf-8"))
        rels = yaml.safe_load((directory / "relationships.yaml").read_text(encoding="utf-8"))
        terms = yaml.safe_load((directory / "business_terms.yaml").read_text(encoding="utf-8"))
        metrics = {
            name: Metric(
                name=name,
                description=m["description"],
                base_table=m["base_table"],
                expression=m["expression"],
                where=m.get("where"),
                requires=tuple(m.get("requires", ())),
                synonyms=tuple(m.get("synonyms", ())),
            )
            for name, m in raw["metrics"].items()
        }
        dimensions = {
            name: Dimension(
                name=name,
                description=d["description"],
                sources=tuple(
                    DimensionSource(s["table"], s.get("column"), s.get("expression")) for s in d["sources"]
                ),
                synonyms=tuple(d.get("synonyms", ())),
                ordered_by_dimension=bool(d.get("ordered_by_dimension", False)),
            )
            for name, d in raw["dimensions"].items()
        }
        parents: dict[str, list[tuple[str, str, str]]] = {}
        for rel in rels["relationships"]:
            child_table, child_col = rel["child"].split(".")
            parent_table, parent_col = rel["parent"].split(".")
            parents.setdefault(child_table, []).append((child_col, parent_table, parent_col))
        return cls(metrics, dimensions, parents, terms["terms"], raw["default_limit"], raw["max_limit"])

    # joins
    def join_path(self, base: str, target: str, allowed: Collection[str]) -> list[Join] | None:
        """Joins from ``base`` up to ``target`` through allowed parent tables, or None when unreachable."""
        if target == base:
            return []
        queue: deque[tuple[str, list[Join]]] = deque([(base, [])])
        seen = {base}
        while queue:
            table, path = queue.popleft()
            for child_col, parent_table, parent_col in self.parents.get(table, []):
                if parent_table in seen or parent_table not in allowed:
                    continue
                step = [*path, Join(parent_table, f"{table}.{child_col} = {parent_table}.{parent_col}")]
                if parent_table == target:
                    return step
                seen.add(parent_table)
                queue.append((parent_table, step))
        return None

    def resolve_dimension(
        self, metric: Metric, dimension: Dimension, allowed: Collection[str]
    ) -> tuple[DimensionSource, list[Join]] | None:
        """Pick the source of a dimension: the metric's own table first, then the first reachable one."""
        ordered = sorted(dimension.sources, key=lambda s: s.table != metric.base_table)  # stable sort
        for source in ordered:
            if source.table not in allowed:
                continue
            path = self.join_path(metric.base_table, source.table, allowed)
            if path is not None:
                return source, path
        return None

    # planning
    def plan(
        self,
        metric_name: str,
        dimension_names: tuple[str, ...] = (),
        *,
        allowed_tables: Collection[str],
        allowed_metrics: Collection[str] | None = None,
        limit: int | None = None,
        ranked: bool = False,
    ) -> PlannedQuery:
        if metric_name not in self.metrics:
            raise NoMetricFound(f"Unknown metric: {metric_name}")
        metric = self.metrics[metric_name]
        if allowed_metrics is not None and metric_name not in allowed_metrics:
            raise MetricNotAvailable(self._not_available("metric", metric_name, sorted(allowed_metrics)))
        missing = metric.tables - set(allowed_tables)
        if missing:
            raise MetricNotAvailable(
                f"'{metric_name.replace('_', ' ')}' needs the table(s) {', '.join(sorted(missing))}, "
                "which are not part of your mission's dataset."
            )
        if len(dimension_names) > MAX_DIMENSIONS:
            raise DimensionNotAvailable(f"Please use at most {MAX_DIMENSIONS} breakdowns at a time.")
        selects, group_by, joins, order_dim = [], [], {}, False
        for name in dimension_names:
            dimension = self.dimensions[name]
            resolved = self.resolve_dimension(metric, dimension, allowed_tables)
            if resolved is None:
                raise DimensionNotAvailable(
                    f"'{metric_name.replace('_', ' ')}' cannot be broken down by {name.replace('_', ' ')} "
                    "with the tables of your mission."
                )
            source, path = resolved
            for join in path:
                joins.setdefault(join.table, join)
            selects.append(f"{source.sql} AS {name}")
            group_by.append(source.sql)
            order_dim = order_dim or dimension.ordered_by_dimension
        selects.append(f"{metric.expression} AS {metric_name}")
        sql = f"SELECT {', '.join(selects)} FROM {metric.base_table}"
        for join in joins.values():
            sql += f" JOIN {join.table} ON {join.on}"
        if metric.where:
            sql += f" WHERE {metric.where}"
        if group_by:
            sql += f" GROUP BY {', '.join(group_by)}"
            by_dimension = order_dim and not ranked  # an explicit "top N" always means highest first
            sql += f" ORDER BY {', '.join(group_by)}" if by_dimension else f" ORDER BY {metric_name} DESC"
        row_limit = min(limit or self.default_limit, self.max_limit)
        sql += f" LIMIT {row_limit}"
        used = {metric.base_table, *metric.requires, *joins}
        return PlannedQuery(sql, metric_name, tuple(dimension_names), frozenset(used))

    # questions
    @staticmethod
    def _find(phrases: tuple[str, ...], text: str) -> int | None:
        best = None
        for phrase in phrases:
            match = re.search(rf"\b{re.escape(phrase.lower())}\b", text)
            if match and (best is None or len(phrase) > best):
                best = len(phrase)
        return best

    def match_metric(self, text: str) -> Metric | None:
        scored = [(self._find(m.phrases, text), m) for m in self.metrics.values()]
        scored = [(score, m) for score, m in scored if score]
        return max(scored, key=lambda s: (s[0], s[1].name))[1] if scored else None

    def match_dimensions(self, tail: str) -> list[str]:
        found: list[tuple[int, int, str]] = []
        for name, d in self.dimensions.items():
            best = None
            for phrase in d.phrases:
                match = re.search(rf"\b{re.escape(phrase.lower())}\b", tail)
                if match and (best is None or len(phrase) > best[1]):
                    best = (match.start(), len(phrase))
            if best:
                found.append((best[0], best[1], name))
        # a longer phrase wins over a shorter one it contains (e.g. "branch name" over "branch")
        kept = [
            f
            for f in found
            if not any(
                o is not f and o[0] <= f[0] and o[0] + o[1] >= f[0] + f[1] and o[1] > f[1] for o in found
            )
        ]
        return [name for _start, _length, name in sorted(kept)]

    def resolve_question(
        self,
        question: str,
        *,
        allowed_tables: Collection[str],
        allowed_metrics: Collection[str],
    ) -> PlannedQuery:
        text = " ".join(question.lower().split()).rstrip("?.! ")
        top = re.search(r"\b(?:top|first)\s+(\d{1,3})\b", text)
        limit = int(top.group(1)) if top else None
        text = re.sub(r"\b(?:top|first)\s+\d{1,3}\b", " ", text)
        head, separator, tail = (
            re.split(r"\s+(by|per|for each)\s+", text, maxsplit=1)
            if re.search(r"\s+(by|per|for each)\s+", text)
            else (text, "", "")
        )
        metric = self.match_metric(head)
        if metric is None:
            raise NoMetricFound(
                "I could not find a metric in your question. Try one of: "
                + ", ".join(sorted(m.replace("_", " ") for m in allowed_metrics))
                + "."
            )
        dimensions = self.match_dimensions(tail) if separator else []
        if separator and not dimensions:
            raise DimensionNotAvailable(
                "I could not find a breakdown in your question. Examples: "
                + ", ".join(sorted(self.dimensions)[:8]).replace("_", " ")
                + "."
            )
        return self.plan(
            metric.name,
            tuple(dimensions[:MAX_DIMENSIONS]),
            allowed_tables=allowed_tables,
            allowed_metrics=allowed_metrics,
            limit=limit,
            ranked=top is not None,
        )

    def _not_available(self, kind: str, name: str, allowed: list[str]) -> str:
        return (
            f"The {kind} '{name.replace('_', ' ')}' is not part of your mission. "
            f"Available: {', '.join(a.replace('_', ' ') for a in allowed)}."
        )
