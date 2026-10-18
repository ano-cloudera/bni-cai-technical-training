from __future__ import annotations

from bni_training.guardrails import validate_input, validate_sql
from bni_training.semantic import SemanticCatalog, compile_question


class DataQueryTool:
    def __init__(self, backend, catalog: SemanticCatalog, timeout_seconds: int = 30):
        self.backend = backend
        self.catalog = catalog
        self.timeout_seconds = timeout_seconds

    def query(self, question: str):
        question = validate_input(question)
        sql = compile_question(question, self.catalog)
        sql = validate_sql(sql, self.catalog.allowed_tables, default_limit=100)
        return sql, self.backend.execute(sql, self.timeout_seconds)
