from __future__ import annotations

import json
import os
import sys
import tempfile
import warnings

from bni_training.data.bundles import BundleCatalog
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
    "Lab 07: index glossary and mission notes into Qdrant and retrieve with a mandatory group_id filter."
)
QUERY = "What does DPD 30 mean?"


def documents_for(bundle) -> list[dict]:
    glossary = [json.loads(x) for x in GLOSSARY.read_text(encoding="utf-8").splitlines() if x.strip()]
    note = {
        "chunk_id": f"mission-{bundle.mission_id}",
        "title": bundle.mission_title,
        "document_type": "mission",
        "source": "synthetic-workshop",
        "text": f"{bundle.mission_title}. {bundle.mission_objective}",
    }
    return [*glossary, note]


def run_flow(client, ctx, other_bundles, embed_many, embed, report) -> list[dict]:
    """Index this group's partition (and, locally, others) then prove retrieval stays inside the group."""
    for bundle in [ctx.bundle, *other_bundles]:
        result = index_group_documents(client, bundle.group_id, documents_for(bundle), embed_many)
        report.passed(f"index_{bundle.group_id}", f"{result['documents']} documents into {COLLECTION}")
    hits = search_group(client, ctx.group_id, QUERY, embed, limit=5)
    (report.passed if hits else report.failed)(
        "retrieval", f"{len(hits)} hits; top: {hits[0]['title'] if hits else None}"
    )
    leaked = {h["group_id"] for h in hits} - {ctx.group_id}
    (report.failed if leaked else report.passed)(
        "group_isolation", f"hit groups: {sorted({h['group_id'] for h in hits})}"
    )
    mission = search_group(client, ctx.group_id, ctx.bundle.mission_title, embed, limit=5)
    found = any(h["chunk_id"] == f"mission-{ctx.bundle.mission_id}" for h in mission)
    (report.passed if found else report.failed)("mission_note_found", ctx.bundle.mission_title)
    for bundle in other_bundles:
        scoped = retrieve_group_documents(
            client, collection_name=COLLECTION, query_vector=embed(QUERY), group_id=bundle.group_id, limit=20
        )
        groups = {p.payload["group_id"] for p in scoped.points}
        (report.passed if groups == {bundle.group_id} else report.failed)(
            f"strict_filter_{bundle.group_id}", f"groups returned: {sorted(groups)}"
        )
    report.data["filter_rest_json"] = group_filter_json(ctx.group_id)
    return hits


def body(args, report):
    ctx = report.context
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise RuntimeError("Install the rag (or dev-test) dependency profile for lab 07") from exc
    catalog = BundleCatalog.load()
    if args.mode == "local":
        embedder = HashingEmbedder()
        other = catalog.for_group("group_02" if ctx.group_id == "group_01" else "group_01")
        with tempfile.TemporaryDirectory() as tmp, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            client = QdrantClient(path=tmp)
            hits = run_flow(client, ctx, [other], embedder.embed_many, embedder.embed, report)
            client.close()
        report.skipped(
            "qdrant_server", "Local mode uses qdrant-client local storage, not the shared Qdrant Application"
        )
        report.skipped(
            "bge_m3_embeddings",
            "Local mode uses a deterministic hashing embedder; bge-m3 is staged on NFS in CAI",
        )
    else:
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
        hits = run_flow(client, ctx, [], embed_many, lambda text: embed_many([text])[0], report)
    saved = ctx.write_output(
        "07_retrieval.json",
        json.dumps([{k: h[k] for k in ("title", "group_id", "score")} for h in hits], indent=2),
    )
    report.passed("saved", f"groups/{ctx.group_id}/output/{saved.name}")


def main(argv=None) -> int:
    return run_lab("07", DESCRIPTION, body, argv, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
