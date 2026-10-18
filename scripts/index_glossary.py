from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from bni_training.config import validate_group_id

COLLECTION = "bni_training_knowledge"


def build_points(group_id: str, documents: list[dict], vectors: list[list[float]]) -> list[dict]:
    group_id = validate_group_id(group_id)
    if len(documents) != len(vectors):
        raise ValueError("documents and vectors must have the same length")
    points = []
    for document, vector in zip(documents, vectors, strict=True):
        chunk_id = document["chunk_id"]
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"bni-training:{group_id}:{chunk_id}"))
        points.append({"id": point_id, "vector": vector, "payload": {**document, "group_id": group_id}})
    return points


def index_documents(
    group_id: str, documents: list[dict], qdrant_url: str, model_path: str, api_key: str = ""
):
    try:
        from qdrant_client import QdrantClient, models
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install the rag dependency profile before indexing") from exc

    embedder = SentenceTransformer(model_path, device="cpu")
    vectors = embedder.encode([item["text"] for item in documents], normalize_embeddings=True).tolist()
    client = QdrantClient(url=qdrant_url, api_key=api_key or None)
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(size=len(vectors[0]), distance=models.Distance.COSINE),
        )
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name="group_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    points = [models.PointStruct(**point) for point in build_points(group_id, documents, vectors)]
    client.upsert(collection_name=COLLECTION, points=points, wait=True)
    return {"group_id": group_id, "documents": len(points), "collection": COLLECTION}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--glossary", type=Path, default=Path("data/glossary/banking_glossary.jsonl"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    group_id = validate_group_id(args.group_id)
    documents = [json.loads(line) for line in args.glossary.read_text().splitlines() if line.strip()]
    if not args.execute:
        print(
            json.dumps(
                {"group_id": group_id, "documents": len(documents), "collection": COLLECTION, "dry_run": True}
            )
        )
        return 0
    result = index_documents(
        group_id,
        documents,
        os.environ["QDRANT_URL"],
        os.environ["EMBEDDING_MODEL_PATH"],
        os.getenv("QDRANT_API_KEY", ""),
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
