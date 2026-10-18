from typing import Protocol

from bni_training.schemas import HealthStatus, QueryResult


class DataBackend(Protocol):
    def execute(self, sql: str, timeout_seconds: int = 30) -> QueryResult: ...
    def healthcheck(self) -> HealthStatus: ...
