from __future__ import annotations

import json
import threading
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

qdrant_client = pytest.importorskip("qdrant_client")
from qdrant_client import QdrantClient, models  # noqa: E402

from bni_training.rag import (  # noqa: E402
    COLLECTION,
    HashingEmbedder,
    build_group_filter,
    group_filter_json,
    index_group_documents,
    retrieve_group_documents,
    search_group,
)

GLOSSARY = Path("data/glossary/banking_glossary.jsonl")


def documents() -> list[dict]:
    return [json.loads(line) for line in GLOSSARY.read_text().splitlines() if line.strip()]


def test_filter_uses_native_qdrant_models() -> None:
    group_filter = build_group_filter("group_07")
    assert isinstance(group_filter, models.Filter)
    assert isinstance(group_filter.must[0], models.FieldCondition)
    assert isinstance(group_filter.must[0].match, models.MatchValue)


def test_filter_rest_json_is_exact() -> None:
    assert group_filter_json("group_03") == {"must": [{"key": "group_id", "match": {"value": "group_03"}}]}


@pytest.mark.parametrize("bad", ["", "group_00", "group_11", "group_1", "GROUP_01", "other"])
def test_filter_rejects_invalid_group(bad: str) -> None:
    with pytest.raises(ValueError, match="group_01 through group_10"):
        build_group_filter(bad)


def test_rest_request_body_carries_the_group_filter() -> None:
    bodies: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            bodies.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            data = json.dumps({"result": {"points": []}, "status": "ok", "time": 0.0}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = QdrantClient(url=f"http://127.0.0.1:{server.server_port}", check_compatibility=False)
        retrieve_group_documents(
            client, collection_name=COLLECTION, query_vector=[0.1, 0.2], group_id="group_03", limit=4
        )
    finally:
        server.shutdown()
    assert bodies[0]["filter"] == {"must": [{"key": "group_id", "match": {"value": "group_03"}}]}
    assert bodies[0]["limit"] == 4


def test_local_mode_indexes_and_retrieves_with_strict_group_isolation(tmp_path: Path) -> None:
    embedder = HashingEmbedder()
    docs = documents()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = QdrantClient(path=str(tmp_path))
        for group in ("group_01", "group_02", "group_10"):
            result = index_group_documents(client, group, docs, embedder.embed_many)
            assert result["documents"] == len(docs)
        total = client.count(COLLECTION, exact=True).count
        assert total == 3 * len(docs)
        for group in ("group_01", "group_02", "group_10"):
            hits = search_group(client, group, "What does DPD 30 mean?", embedder.embed, limit=20)
            assert len(hits) == len(docs)
            assert {hit["group_id"] for hit in hits} == {group}
            assert hits[0]["title"] == "DPD 30"
        client.close()


def test_retrieval_detects_a_point_outside_the_requested_group() -> None:
    class Point:
        payload = {"group_id": "group_02"}

    class Response:
        points = [Point()]

    class Client:
        def query_points(self, **_kwargs):
            return Response()

    with pytest.raises(RuntimeError, match="outside the requested group_id"):
        retrieve_group_documents(
            Client(), collection_name=COLLECTION, query_vector=[1.0], group_id="group_01"
        )


def test_retrieval_validates_limit_and_vector() -> None:
    class Client:
        def query_points(self, **_kwargs):  # pragma: no cover - must not be reached
            raise AssertionError("query must be rejected before reaching Qdrant")

    with pytest.raises(ValueError):
        retrieve_group_documents(Client(), collection_name="c", query_vector=[], group_id="group_01")
    with pytest.raises(ValueError):
        retrieve_group_documents(
            Client(), collection_name="c", query_vector=[1.0], group_id="group_01", limit=21
        )
