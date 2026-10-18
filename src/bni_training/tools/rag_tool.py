from __future__ import annotations

from bni_training.rag import build_group_filter


class KnowledgeRetrievalTool:
    def __init__(self, client, collection: str, embed):
        self.client = client
        self.collection = collection
        self.embed = embed

    def search(self, group_id: str, query: str, limit: int = 5):
        tenant_filter = build_group_filter(group_id)
        vector = self.embed(query)
        return self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=tenant_filter,
            limit=limit,
            with_payload=True,
        )
