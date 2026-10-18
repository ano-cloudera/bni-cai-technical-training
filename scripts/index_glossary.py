from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from bni_training.config import validate_group_id
from bni_training.rag import COLLECTION, build_points, index_group_documents

__all__ = ["COLLECTION", "build_points", "index_documents", "main"]


def index_documents(
    group_id: str, documents: list[dict], qdrant_url: str, model_path: str, api_key: str = ""
):
    try:
        from qdrant_client import QdrantClient
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install the rag dependency profile before indexing") from exc

    embedder = SentenceTransformer(model_path, device="cpu")

    def embed_many(texts: list[str]) -> list[list[float]]:
        return embedder.encode(texts, normalize_embeddings=True).tolist()

    client = QdrantClient(url=qdrant_url, api_key=api_key or None)
    return index_group_documents(client, group_id, documents, embed_many)


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
