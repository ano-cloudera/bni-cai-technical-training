from __future__ import annotations

import json
import os
import sys
import tempfile
import warnings

from bni_training.config import validate_group_id
from bni_training.labs import GLOSSARY, PrerequisiteMissing, require_env, run_lab
from bni_training.rag import (
    COLLECTION,
    HashingEmbedder,
    group_filter_json,
    index_group_documents,
    retrieve_group_documents,
    search_group,
)

DESCRIPTION = (
    "Lab 07: index the synthetic glossary into Qdrant and retrieve it with mandatory group isolation."
)
QUERY = "What does DPD 30 mean?"
EXPECTED_TITLE = "DPD 30"


def load_documents() -> list[dict]:
    return [json.loads(line) for line in GLOSSARY.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_flow(client, group_id, other_groups, documents, embed_many, embed, report) -> None:
    """Index one partition per group, retrieve for group_id, and prove no other group leaks."""
    for group in [group_id, *other_groups]:
        result = index_group_documents(client, group, documents, embed_many)
        report.passed(f"index_{group}", f"{result['documents']} documents into {COLLECTION}")
    hits = search_group(client, group_id, QUERY, embed, limit=3)
    (report.passed if hits else report.failed)(
        "retrieval", f"{len(hits)} hits; top: {hits[0]['title'] if hits else None}"
    )
    if report.mode == "local" and hits and hits[0]["title"] != EXPECTED_TITLE:
        report.failed("retrieval_relevance", f"expected {EXPECTED_TITLE}, got {hits[0]['title']}")
    leaked = {hit["group_id"] for hit in hits} - {group_id}
    (report.failed if leaked else report.passed)(
        "group_isolation", f"hit groups: {sorted({h['group_id'] for h in hits})}"
    )
    for other in other_groups:
        scoped = retrieve_group_documents(
            client, collection_name=COLLECTION, query_vector=embed(QUERY), group_id=other, limit=20
        )
        groups = {p.payload["group_id"] for p in scoped.points}
        (report.passed if groups == {other} else report.failed)(
            f"strict_filter_{other}", f"groups returned: {sorted(groups)}"
        )
    report.data["filter_rest_json"] = group_filter_json(group_id)


def body(args, report):
    group_id = validate_group_id(os.getenv("GROUP_ID", "group_01"))
    documents = load_documents()
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("Install the rag (or dev-test) dependency profile for lab 07") from exc
    if args.mode == "local":
        embedder = HashingEmbedder()
        with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            client = QdrantClient(path=tmp)  # local on-disk mode, complete code path without a server
            run_flow(client, group_id, ["group_02"], documents, embedder.embed_many, embedder.embed, report)
            client.close()
        report.skipped(
            "qdrant_server", "Local mode uses qdrant-client local storage, not the shared Qdrant Application"
        )
        report.skipped(
            "bge_m3_embeddings",
            "Local mode uses a deterministic hashing embedder; bge-m3 is staged on NFS in CAI",
        )
        return
    env = require_env(["QDRANT_URL", "EMBEDDING_MODEL_PATH"])
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Install the rag dependency profile for lab 07") from exc
    if not os.path.isdir(env["EMBEDDING_MODEL_PATH"]):
        raise PrerequisiteMissing("EMBEDDING_MODEL_PATH is not a directory on NFS")
    model = SentenceTransformer(env["EMBEDDING_MODEL_PATH"], device="cpu")

    def embed_many(texts):
        return model.encode(list(texts), normalize_embeddings=True).tolist()

    client = QdrantClient(url=env["QDRANT_URL"], api_key=os.getenv("QDRANT_API_KEY") or None)
    run_flow(client, group_id, [], documents, embed_many, lambda text: embed_many([text])[0], report)


def main(argv=None) -> int:
    return run_lab("07", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
