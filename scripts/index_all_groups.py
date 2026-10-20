"""Trainer: index the glossary and the mission note of every group into the shared Qdrant collection.

Dry run by default (nothing is written). With --execute it embeds with the bge-m3 model on NFS and upserts one
partition per group; every point carries its own ``group_id``, so a group never overwrites another. Safe to repeat.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from bni_training.config import validate_group_id
from bni_training.data.bundles import BundleCatalog
from bni_training.labs import GLOSSARY
from bni_training.rag import COLLECTION, index_group_documents

QDRANT_TIMEOUT_S = 60


def documents_for(bundle) -> list[dict]:
    """The same documents lab 07 indexes for a group: the glossary plus the mission note."""
    glossary = [json.loads(line) for line in GLOSSARY.read_text(encoding="utf-8").splitlines() if line.strip()]
    note = {
        "chunk_id": f"mission-{bundle.mission_id}",
        "title": bundle.mission_title,
        "document_type": "mission",
        "source": "synthetic-workshop",
        "text": f"{bundle.mission_title}. {bundle.mission_objective}",
    }
    return [*glossary, note]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--group-id", action="append", help="Only this group (repeatable). Default: all ten")
    parser.add_argument("--execute", action="store_true", help="Write to Qdrant (the default is a dry run)")
    args = parser.parse_args(argv)
    catalog = BundleCatalog.load()
    group_ids = [validate_group_id(item) for item in (args.group_id or sorted(catalog.bundles))]
    plan = {group_id: documents_for(catalog.bundles[group_id]) for group_id in group_ids}
    if not args.execute:
        summary = {group_id: len(documents) for group_id, documents in plan.items()}
        print(json.dumps({"dry_run": True, "collection": COLLECTION, "documents_per_group": summary}, indent=2))
        return 0
    for name in ("QDRANT_URL", "EMBEDDING_MODEL_PATH"):
        if not os.environ.get(name):
            print(f"{name} is not set", file=sys.stderr)
            return 2
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(os.environ["EMBEDDING_MODEL_PATH"], device="cpu")

    def embed_many(texts):
        return model.encode(list(texts), normalize_embeddings=True).tolist()

    client = QdrantClient(
        url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY") or None, timeout=QDRANT_TIMEOUT_S
    )
    for group_id, documents in plan.items():
        print(json.dumps(index_group_documents(client, group_id, documents, embed_many)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
