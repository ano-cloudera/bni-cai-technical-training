"""The participant data tool: one tool per group bundle (CrewAI-compatible ``query``)."""

from __future__ import annotations

from dataclasses import dataclass

from bni_training.user_errors import UserFacingError

from .bundles import GroupBundle
from .engine import CsvEngine, WorkshopQueryResult
from .semantic_layer import SemanticModel


class CrossGroupAccessError(UserFacingError, PermissionError):
    """A request named a group, dataset or mission that is not this tool's bundle."""


@dataclass(frozen=True)
class DataRequest:
    """Identity carried by every data request."""

    group_id: str
    session_id: str
    dataset_id: str
    mission_id: str


class RequestBoundTool:
    """Adds a fixed request identity to ``query`` so frameworks that call ``query(question)`` stay scoped."""

    def __init__(self, tool: "WorkshopDataTool", request: DataRequest):
        self._tool, self.request = tool, request

    def query(self, question: str):
        return self._tool.query(question, self.request)


class WorkshopDataTool:
    def __init__(self, engine: CsvEngine, semantic: SemanticModel, bundle: GroupBundle, max_rows: int = 200):
        self._engine, self._semantic, self.bundle, self._max_rows = engine, semantic, bundle, max_rows

    def _check(self, request: DataRequest | None) -> None:
        if request is None:
            return
        b = self.bundle
        if (request.group_id, request.dataset_id, request.mission_id) != (
            b.group_id,
            b.dataset_id,
            b.mission_id,
        ):
            raise CrossGroupAccessError("That dataset or mission is not assigned to your group.")

    def query(self, question: str, request: DataRequest | None = None) -> tuple[str, WorkshopQueryResult]:
        """Answer a business question with the semantic layer. Returns (sql, result)."""
        self._check(request)
        plan = self._semantic.resolve_question(
            question, allowed_tables=self.bundle.tables, allowed_metrics=self.bundle.allowed_metrics
        )
        return plan.sql, self._engine.query(plan.sql, self.bundle.policy, max_rows=self._max_rows)

    def run_sql(self, sql: str, request: DataRequest | None = None) -> WorkshopQueryResult:
        """Run participant SQL against the bundle's tables only (read-only, capped)."""
        self._check(request)
        return self._engine.query(sql, self.bundle.policy, max_rows=self._max_rows)

    def bind(self, request: DataRequest) -> RequestBoundTool:
        self._check(request)
        return RequestBoundTool(self, request)

    def describe(self) -> dict:
        """What this group may use. Safe to show to participants."""
        tables = {}
        for name in self.bundle.tables:
            table = self._engine.dictionary.tables[name]
            tables[name] = {
                "description": table.description,
                "columns": {c: table.column(c).description for c in table.exposed_columns},
            }
        return {
            "group_id": self.bundle.group_id,
            "dataset_id": self.bundle.dataset_id,
            "mission_id": self.bundle.mission_id,
            "mission_title": self.bundle.mission_title,
            "tables": tables,
            "metrics": {m: self._semantic.metrics[m].description for m in self.bundle.allowed_metrics},
        }
