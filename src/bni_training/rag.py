from __future__ import annotations

import hashlib
import os
import re
import uuid
from collections.abc import Callable, Sequence
from typing import Any

from .config import validate_group_id

COLLECTION = "bni_training_knowledge"
GROUP_FIELD = "group_id"


def _models() -> Any:
    try:
        from qdrant_client import models
    except ImportError as exc:
        raise RuntimeError("Install the rag or dev-test dependency profile to use Qdrant") from exc
    return models


def build_group_filter(group_id: str) -> Any:
    """Return the mandatory native qdrant-client group filter.

    The native model serializes to the REST JSON ``{"must": [{"key": "group_id",
    "match": {"value": "<group>"}}]}`` and is accepted by both server and local mode.
    """
    models = _models()
    return models.Filter(
        must=[
            models.FieldCondition(
                key=GROUP_FIELD,
                match=models.MatchValue(value=validate_group_id(group_id)),
            )
        ]
    )


def group_filter_json(group_id: str) -> dict:
    """REST JSON representation of the group filter, for logs and assertions."""
    return build_group_filter(group_id).model_dump(exclude_none=True)


def retrieve_group_documents(
    client: Any,
    *,
    collection_name: str,
    query_vector: list[float],
    group_id: str,
    limit: int = 5,
) -> Any:
    """Run a Qdrant query that cannot omit workshop group isolation."""
    if not query_vector:
        raise ValueError("query_vector cannot be empty")
    if limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    group_id = validate_group_id(group_id)
    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=build_group_filter(group_id),
        limit=limit,
        with_payload=True,
    )
    for point in getattr(response, "points", []):
        if (point.payload or {}).get(GROUP_FIELD) != group_id:
            raise RuntimeError("Qdrant returned a point outside the requested group_id")
    return response


class HashingEmbedder:
    """Deterministic bag-of-words embedder for local mode. It is a stand-in, not bge-m3."""

    name = "hashing-bow-local"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dim] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class SentenceTransformerEmbedder:
    """The embedder the trainer indexes with (bge-m3 on CPU). The model folder comes from EMBEDDING_MODEL_PATH on NFS."""

    def __init__(self, model_path: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is missing: choose the 'BNI rag' kernel") from exc
        self._model = SentenceTransformer(model_path, device="cpu")
        self.name = os.path.basename(os.path.normpath(model_path))
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [[float(value) for value in vector] for vector in vectors]


def build_points(group_id: str, documents: list[dict], vectors: list[list[float]]) -> list[dict]:
    group_id = validate_group_id(group_id)
    if len(documents) != len(vectors):
        raise ValueError("documents and vectors must have the same length")
    points = []
    for document, vector in zip(documents, vectors, strict=True):
        chunk_id = document["chunk_id"]
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bni-training:{group_id}:{chunk_id}"))
        points.append({"id": point_id, "vector": vector, "payload": {**document, GROUP_FIELD: group_id}})
    return points


def ensure_collection(client: Any, vector_size: int, collection_name: str = COLLECTION) -> None:
    models = _models()
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
    client.create_payload_index(
        collection_name=collection_name,
        field_name=GROUP_FIELD,
        field_schema=models.PayloadSchemaType.KEYWORD,
    )


def index_group_documents(
    client: Any,
    group_id: str,
    documents: list[dict],
    embed_many: Callable[[list[str]], list[list[float]]],
    collection_name: str = COLLECTION,
) -> dict:
    """Embed and upsert one group partition into the shared collection."""
    models = _models()
    group_id = validate_group_id(group_id)
    vectors = [list(map(float, vector)) for vector in embed_many([item["text"] for item in documents])]
    ensure_collection(client, len(vectors[0]), collection_name)
    points = [models.PointStruct(**point) for point in build_points(group_id, documents, vectors)]
    client.upsert(collection_name=collection_name, points=points, wait=True)
    return {"group_id": group_id, "documents": len(points), "collection": collection_name}


def search_group(
    client: Any,
    group_id: str,
    query: str,
    embed: Callable[[str], list[float]],
    *,
    limit: int = 3,
    collection_name: str = COLLECTION,
) -> list[dict]:
    response = retrieve_group_documents(
        client,
        collection_name=collection_name,
        query_vector=list(map(float, embed(query))),
        group_id=group_id,
        limit=limit,
    )
    return [{"score": point.score, **(point.payload or {})} for point in response.points]
