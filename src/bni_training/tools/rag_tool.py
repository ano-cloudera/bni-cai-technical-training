from __future__ import annotations

from bni_training.rag import search_group


class KnowledgeRetrievalTool:
    def __init__(self, client, collection: str, embed):
        self.client = client
        self.collection = collection
        self.embed = embed

    def search(self, group_id: str, query: str, limit: int = 5):
        return search_group(
            self.client, group_id, query, self.embed, limit=limit, collection_name=self.collection
        )
