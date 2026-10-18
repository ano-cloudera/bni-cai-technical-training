from .config import validate_group_id


def build_group_filter(group_id: str) -> dict:
    group_id = validate_group_id(group_id)
    return {"must": [{"key": "group_id", "match": {"value": group_id}}]}


def retrieve_group_documents(
    client,
    *,
    collection_name: str,
    query_vector: list[float],
    group_id: str,
    limit: int = 5,
):
    """Run a Qdrant query that cannot omit workshop group isolation."""
    if not query_vector:
        raise ValueError("query_vector cannot be empty")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    return client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=build_group_filter(group_id),
        limit=limit,
        with_payload=True,
    )
