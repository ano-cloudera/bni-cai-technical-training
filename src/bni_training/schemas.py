from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImmutableModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class QueryResult(ImmutableModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int = 0
    elapsed_ms: float = 0


class HealthStatus(ImmutableModel):
    healthy: bool
    service: str
    detail: str = ""


class SemanticQuery(ImmutableModel):
    metric: str
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 100


class AgentAnswer(ImmutableModel):
    answer: str
    query: str
    data: QueryResult
    citations: list[str] = Field(default_factory=list)


class TraceContext(ImmutableModel):
    group_id: str
    session_id: str
    request_name: str
