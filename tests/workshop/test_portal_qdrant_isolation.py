from __future__ import annotations

import warnings

import pytest

qdrant_client = pytest.importorskip("qdrant_client")

from qdrant_client import QdrantClient  # noqa: E402

from bni_training.rag import HashingEmbedder, build_group_filter, index_group_documents  # noqa: E402
from bni_training.workshop.portal.service import RetrievalUnavailable  # noqa: E402

GROUPS = [f"group_{i:02d}" for i in range(1, 11)]


@pytest.fixture
def indexed():
    embedder = HashingEmbedder()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = QdrantClient(":memory:")
        for group in GROUPS:
            docs = [
                {
                    "chunk_id": f"secret-{group}",
                    "title": f"Private note of {group}",
                    "document_type": "note",
                    "source": "synthetic-workshop",
                    "text": f"shared quarterly portfolio review confidential {group}",
                },
                {
                    "chunk_id": "common",
                    "title": "Common glossary",
                    "document_type": "glossary",
                    "source": "synthetic-workshop",
                    "text": "shared quarterly portfolio review glossary entry",
                },
            ]
            index_group_documents(client, group, docs, embedder.embed_many)
    yield client, embedder
    client.close()


def test_every_group_only_ever_retrieves_its_own_documents(make_service, indexed) -> None:
    client, embedder = indexed
    service = make_service(qdrant=client, embed=embedder.embed)
    for group in GROUPS:
        ctx = service.open_session(group)
        for other in GROUPS:  # even a query that names another group's private note
            hits = service.retrieve(ctx, f"shared quarterly portfolio review confidential {other}", limit=20)
            assert hits, group
            assert {h["group_id"] for h in hits} == {group}
            assert not any(h["chunk_id"].startswith("secret-") and h["group_id"] != group for h in hits)
            assert f"secret-{other}" not in {h["chunk_id"] for h in hits} or other == group


def test_two_sessions_of_one_group_share_the_group_partition_but_nothing_else(make_service, indexed) -> None:
    client, embedder = indexed
    service = make_service(qdrant=client, embed=embedder.embed)
    a, b = service.open_session("group_04"), service.open_session("group_04")
    assert {h["group_id"] for h in service.retrieve(a, "portfolio review")} == {"group_04"}
    ids = [h["chunk_id"] for h in service.retrieve(a, "portfolio review")]
    assert ids == [h["chunk_id"] for h in service.retrieve(b, "portfolio review")]


def test_the_filter_is_built_from_the_session_group_not_from_user_input(make_service, indexed) -> None:
    client, embedder = indexed
    service = make_service(qdrant=client, embed=embedder.embed)
    ctx = service.open_session("group_02")
    hits = service.retrieve(ctx, "group_09 group_09 group_09 confidential group_09", limit=20)
    assert {h["group_id"] for h in hits} == {"group_02"}
    assert build_group_filter(ctx.group_id).must[0].match.value == "group_02"


def test_retrieval_is_reported_unavailable_not_silently_empty(make_service) -> None:
    service = make_service()
    with pytest.raises(RetrievalUnavailable):
        service.retrieve(service.open_session("group_01"), "anything")
