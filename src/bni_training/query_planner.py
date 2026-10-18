from bni_training.semantic import SemanticCatalog, compile_query, resolve_question


def plan_question(question: str, catalog: SemanticCatalog, llm=None) -> tuple[str, object]:
    semantic_query = resolve_question(question, catalog, llm)
    return compile_query(semantic_query, catalog), semantic_query
